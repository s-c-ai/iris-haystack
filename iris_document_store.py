import json
import logging
from typing import Any, Dict, List, Optional

import intersystems_irispython as iris_driver
from haystack import Document, default_from_dict, default_to_dict
from haystack.document_stores.types import DuplicatePolicy

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384


class IRISDocumentStore:
    """
    DocumentStore customizado para InterSystems IRIS no Haystack 2.x.
    Suporta armazenamento de documentos com metadados e busca vetorial
    via VECTOR_COSINE nativo do IRIS.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1972,
        namespace: str = "USER",
        username: str = "demo",
        password: str = "demo",
        table_name: str = "HaystackDocuments",
        embedding_dim: int = EMBEDDING_DIM,
    ):
        self.host = host
        self.port = port
        self.namespace = namespace
        self.username = username
        self.password = password
        self.table_name = table_name
        self.embedding_dim = embedding_dim

        self._conn = self._connect()
        self._create_table_if_not_exists()

    def _connect(self):
        """Cria a conexão com o IRIS via DB-API."""
        conn_str = (
            f"iris://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.namespace}"
        )
        conn = iris_driver.connect(conn_str)
        logger.info("Conectado ao IRIS em %s:%s/%s", self.host, self.port, self.namespace)
        return conn

    def _cursor(self):
        return self._conn.cursor()

    def _create_table_if_not_exists(self):
        """
        Cria a tabela com suporte a vetores nativos do IRIS.
        A coluna EMBEDDING usa o tipo %Library.Vector(DATATYPE="DOUBLE", LEN=<dim>).
        """
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id          VARCHAR(128)  NOT NULL PRIMARY KEY,
            content     LONGVARCHAR,
            meta        LONGVARCHAR,
            score       DOUBLE,
            embedding   VECTOR(DOUBLE, {self.embedding_dim})
        )
        """
        cur = self._cursor()
        cur.execute(ddl)
        self._conn.commit()
        logger.info("Tabela '%s' pronta.", self.table_name)

    def count_documents(self) -> int:
        cur = self._cursor()
        cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
        row = cur.fetchone()
        return row[0] if row else 0

    def filter_documents(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Retorna documentos que correspondem aos filtros.
        Suporta filtros simples no campo 'meta' (JSON).
        """
        cur = self._cursor()

        where_clause = ""
        params = []

        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(f"JSON_VALUE(meta, '$.{key}') = ?")
                params.append(str(value))
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"SELECT id, content, meta, score, embedding FROM {self.table_name} {where_clause}"
        cur.execute(query, params)
        return [self._row_to_document(row) for row in cur.fetchall()]

    def write_documents(
        self,
        documents: List[Document],
        policy: DuplicatePolicy = DuplicatePolicy.NONE,
    ) -> int:
        if policy == DuplicatePolicy.NONE:
            policy = DuplicatePolicy.FAIL

        written = 0
        cur = self._cursor()

        for doc in documents:
            existing = self._get_by_id(doc.id, cur)

            if existing:
                if policy == DuplicatePolicy.FAIL:
                    raise ValueError(
                        f"Documento com id='{doc.id}' já existe. "
                        "Use DuplicatePolicy.SKIP ou OVERWRITE."
                    )
                if policy == DuplicatePolicy.SKIP:
                    continue
                cur.execute(
                    f"DELETE FROM {self.table_name} WHERE id = ?", [doc.id]
                )

            embedding_str = self._embedding_to_str(doc.embedding)
            meta_str = json.dumps(doc.meta or {})

            if embedding_str:
                cur.execute(
                    f"""
                    INSERT INTO {self.table_name} (id, content, meta, score, embedding)
                    VALUES (?, ?, ?, ?, TO_VECTOR(?, DOUBLE))
                    """,
                    [doc.id, doc.content, meta_str, doc.score, embedding_str],
                )
            else:
                cur.execute(
                    f"""
                    INSERT INTO {self.table_name} (id, content, meta, score)
                    VALUES (?, ?, ?, ?)
                    """,
                    [doc.id, doc.content, meta_str, doc.score],
                )

            written += 1

        self._conn.commit()
        return written

    def delete_documents(self, document_ids: List[str]) -> None:
        if not document_ids:
            return
        placeholders = ",".join(["?"] * len(document_ids))
        cur = self._cursor()
        cur.execute(
            f"DELETE FROM {self.table_name} WHERE id IN ({placeholders})",
            document_ids,
        )
        self._conn.commit()

    def embedding_retrieval(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Busca semântica usando VECTOR_COSINE nativo do IRIS.
        """
        query_str = self._embedding_to_str(query_embedding)

        where_clause = "WHERE embedding IS NOT NULL"
        params: List[Any] = [query_str, top_k]

        if filters:
            for key, value in filters.items():
                where_clause += f" AND JSON_VALUE(meta, '$.{key}') = ?"
                params.insert(-1, str(value)) 

        query = f"""
            SELECT TOP ?
                id, content, meta, score, embedding,
                VECTOR_COSINE(embedding, TO_VECTOR(?, DOUBLE)) AS similarity
            FROM {self.table_name}
            {where_clause}
            ORDER BY similarity DESC
        """
        params = [top_k, query_str] + (
            [str(v) for v in (filters or {}).values()]
        )

        cur = self._cursor()
        cur.execute(query, params)

        docs = []
        for row in cur.fetchall():
            doc = self._row_to_document(row)
            doc.score = float(row[5]) if row[5] is not None else None
            docs.append(doc)
        return docs
    
    def to_dict(self) -> Dict[str, Any]:
        return default_to_dict(
            self,
            host=self.host,
            port=self.port,
            namespace=self.namespace,
            username=self.username,
            table_name=self.table_name,
            embedding_dim=self.embedding_dim,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IRISDocumentStore":
        return default_from_dict(cls, data)
    
    def _get_by_id(self, doc_id: str, cur=None) -> Optional[Any]:
        _cur = cur or self._cursor()
        _cur.execute(
            f"SELECT id FROM {self.table_name} WHERE id = ?", [doc_id]
        )
        return _cur.fetchone()

    @staticmethod
    def _embedding_to_str(embedding: Optional[List[float]]) -> Optional[str]:
        if embedding is None:
            return None
        return "[" + ",".join(str(v) for v in embedding) + "]"

    @staticmethod
    def _row_to_document(row) -> Document:
        doc_id, content, meta_str, score, *_ = row
        meta = json.loads(meta_str) if meta_str else {}
        return Document(
            id=doc_id,
            content=content,
            meta=meta,
            score=float(score) if score is not None else None,
        )