import dataclasses
import json
import logging
from typing import Any, Dict, List, Optional

import iris
from haystack import Document, default_from_dict, default_to_dict
from haystack.document_stores.types import DuplicatePolicy

logger = logging.getLogger(__name__)


class IRISDocumentStore:
    """
    DocumentStore para InterSystems IRIS compatível com Haystack 2.x.

    Funcionalidades:
    - Armazena documentos com conteúdo, metadados e embeddings vetoriais
    - Busca vetorial nativa via VECTOR_COSINE do IRIS
    - Filtros por campos de metadados (JSON)
    - Suporte completo ao protocolo DocumentStore do Haystack 2.x

    Exemplo de uso:
        store = IRISDocumentStore(
            host="localhost",
            port=1972,
            namespace="USER",
            username="_system",
            password="SYS",
            embedding_dim=384,
        )
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1972,
        namespace: str = "USER",
        username: str = "_system",
        password: str = "SYS",
        table_name: str = "HaystackDocuments",
        embedding_dim: int = 384,
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
        """
        Estabelece conexão com o IRIS via DB-API oficial.
        String de conexão: "host:porta/namespace"
        """
        connection_string = f"{self.host}:{self.port}/{self.namespace}"
        conn = iris.connect(connection_string, self.username, self.password)
        logger.info(
            "Conectado ao IRIS: %s:%s/%s", self.host, self.port, self.namespace
        )
        return conn

    def _cursor(self):
        """Retorna um novo cursor para execução de SQL."""
        return self._conn.cursor()

    def _create_table_if_not_exists(self):
        """
        Cria a tabela de documentos com suporte a vetores nativos.

        Tipos usados:
          - LONGVARCHAR  : texto longo (conteúdo e metadados JSON)
          - VECTOR(DOUBLE, N) : vetor de N dimensões (embedding)
        """
        ddl = f"""
        CREATE TABLE IF NOT EXISTS SQLUser.{self.table_name} (
            id        VARCHAR(128)  NOT NULL PRIMARY KEY,
            content   LONGVARCHAR,
            meta      LONGVARCHAR,
            score     DOUBLE,
            embedding VECTOR(DOUBLE, {self.embedding_dim})
        )
        """
        cur = self._cursor()
        try:
            cur.execute(ddl)
            self._conn.commit()
            logger.info("Tabela 'SQLUser.%s' pronta.", self.table_name)
        except Exception as e:
            logger.warning("Aviso na criação da tabela: %s", e)
        finally:
            cur.close()

    def count_documents(self) -> int:
        """Retorna o total de documentos armazenados."""
        cur = self._cursor()
        try:
            cur.execute(f"SELECT COUNT(*) FROM SQLUser.{self.table_name}")
            row = cur.fetchone()
            return int(row[0]) if row else 0
        finally:
            cur.close()

    def filter_documents(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Retorna documentos filtrados por campos de metadados.

        Usa LIKE na coluna meta (JSON serializado como string) para
        compatibilidade com todas as versões do IRIS Community Edition,
        que não inclui JSON_VALUE como função SQL nativa.

        Args:
            filters: Dicionário chave-valor. Exemplo:
                     {"categoria": "tecnologia", "autor": "joao"}

        Returns:
            Lista de objetos Document do Haystack.
        """
        cur = self._cursor()
        try:
            where_clause = ""
            params = []

            if filters:
                conditions = []
                for key, value in filters.items():
                    pattern = f'%"{key}": "{value}"%'
                    conditions.append("meta LIKE ?")
                    params.append(pattern)
                where_clause = "WHERE " + " AND ".join(conditions)

            query = (
                f"SELECT id, content, meta, score, embedding "
                f"FROM SQLUser.{self.table_name} {where_clause}"
            )
            cur.execute(query, params)
            rows = cur.fetchall()
            return [self._row_to_document(row) for row in rows]
        finally:
            cur.close()

    def write_documents(
        self,
        documents: List[Document],
        policy: DuplicatePolicy = DuplicatePolicy.NONE,
    ) -> int:
        """
        Persiste uma lista de documentos no IRIS.

        Args:
            documents: Lista de Document do Haystack.
            policy: Comportamento para IDs duplicados:
                    - FAIL    : lança exceção (padrão)
                    - SKIP    : ignora o duplicado
                    - OVERWRITE: substitui o documento existente

        Returns:
            Número de documentos efetivamente gravados.
        """
        if policy == DuplicatePolicy.NONE:
            policy = DuplicatePolicy.FAIL

        written = 0
        cur = self._cursor()

        try:
            for doc in documents:
                existing = self._get_by_id(doc.id, cur)

                if existing:
                    if policy == DuplicatePolicy.FAIL:
                        raise ValueError(
                            f"Documento id='{doc.id}' já existe. "
                            "Use DuplicatePolicy.SKIP ou OVERWRITE."
                        )
                    if policy == DuplicatePolicy.SKIP:
                        logger.debug("Ignorando duplicado: %s", doc.id)
                        continue
                    cur.execute(
                        f"DELETE FROM SQLUser.{self.table_name} WHERE id = ?",
                        [doc.id],
                    )

                meta_str = json.dumps(doc.meta or {}, ensure_ascii=False)
                embedding_str = self._embedding_to_str(doc.embedding)

                if embedding_str:
                    cur.execute(
                        f"""
                        INSERT INTO SQLUser.{self.table_name}
                            (id, content, meta, score, embedding)
                        VALUES (?, ?, ?, ?, TO_VECTOR(?, DOUBLE))
                        """,
                        [
                            doc.id,
                            doc.content or "",
                            meta_str,
                            doc.score,
                            embedding_str,
                        ],
                    )
                else:
                    cur.execute(
                        f"""
                        INSERT INTO SQLUser.{self.table_name}
                            (id, content, meta, score)
                        VALUES (?, ?, ?, ?)
                        """,
                        [doc.id, doc.content or "", meta_str, doc.score],
                    )

                written += 1

            self._conn.commit()
            logger.info("%d documento(s) gravado(s).", written)
            return written

        except Exception:
            self._conn.rollback()
            raise
        finally:
            cur.close()

    def delete_documents(self, document_ids: List[str]) -> None:
        """
        Remove documentos pelo ID.

        Args:
            document_ids: Lista de IDs a remover.
        """
        if not document_ids:
            return

        placeholders = ",".join(["?"] * len(document_ids))
        cur = self._cursor()
        try:
            cur.execute(
                f"DELETE FROM SQLUser.{self.table_name} WHERE id IN ({placeholders})",
                document_ids,
            )
            self._conn.commit()
            logger.info("%d documento(s) removido(s).", len(document_ids))
        finally:
            cur.close()

    def embedding_retrieval(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Busca semântica por similaridade usando VECTOR_COSINE do IRIS.

        Args:
            query_embedding : Vetor de consulta (mesmo dim do armazenado).
            top_k           : Máximo de documentos retornados.
            filters         : Filtros adicionais por metadados.

        Returns:
            Documentos ordenados por similaridade (maior = mais relevante).
        """
        query_str = self._embedding_to_str(query_embedding)
        if not query_str:
            raise ValueError("query_embedding não pode ser None ou vazio.")

        where_parts = ["embedding IS NOT NULL"]
        filter_params = []

        if filters:
            for key, value in filters.items():
                pattern = f'%"{key}": "{value}"%'
                where_parts.append("meta LIKE ?")
                filter_params.append(pattern)

        where_clause = "WHERE " + " AND ".join(where_parts)

        query = f"""
            SELECT TOP ?
                id, content, meta, score, embedding,
                VECTOR_COSINE(embedding, TO_VECTOR(?, DOUBLE)) AS similarity
            FROM SQLUser.{self.table_name}
            {where_clause}
            ORDER BY similarity DESC
        """

        params = [top_k, query_str] + filter_params

        cur = self._cursor()
        try:
            cur.execute(query, params)
            docs = []
            for row in cur.fetchall():
                doc = self._row_to_document(row)
                similarity = float(row[5]) if row[5] is not None else None
                doc = dataclasses.replace(doc, score=similarity)
                docs.append(doc)
            return docs
        finally:
            cur.close()

    def to_dict(self) -> Dict[str, Any]:
        """Serializa o DocumentStore (sem a senha)."""
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
        """Reconstrói o DocumentStore a partir de um dicionário."""
        return default_from_dict(cls, data)

    def _get_by_id(self, doc_id: str, cur=None):
        """Verifica se um documento existe pelo ID."""
        _cur = cur or self._cursor()
        _cur.execute(
            f"SELECT id FROM SQLUser.{self.table_name} WHERE id = ?", [doc_id]
        )
        return _cur.fetchone()

    @staticmethod
    def _embedding_to_str(embedding: Optional[List[float]]) -> Optional[str]:
        """Converte lista de floats para string aceita pelo TO_VECTOR() do IRIS."""
        if not embedding:
            return None
        return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"

    @staticmethod
    def _row_to_document(row) -> Document:
        """Converte uma linha do banco em um objeto Document do Haystack."""
        doc_id = row[0]
        content = row[1]
        meta_str = row[2]
        score = row[3]
        # row[4] = embedding (não reconstruímos por performance)

        meta = json.loads(meta_str) if meta_str else {}
        return Document(
            id=doc_id,
            content=content,
            meta=meta,
            score=float(score) if score is not None else None,
        )

    def close(self):
        """Fecha a conexão com o IRIS."""
        if self._conn:
            self._conn.close()
            logger.info("Conexão com o IRIS encerrada.")

    def __repr__(self):
        return (
            f"IRISDocumentStore("
            f"host={self.host}, port={self.port}, "
            f"namespace={self.namespace}, "
            f"table={self.table_name}, "
            f"embedding_dim={self.embedding_dim})"
        )