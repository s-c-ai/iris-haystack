from typing import Any, Dict, List, Optional

from haystack import Document, component, default_from_dict, default_to_dict

from iris_document_store import IRISDocumentStore


@component
class IRISEmbeddingRetriever:
    """
    Retriever semântico que usa VECTOR_COSINE do IRIS para
    encontrar os documentos mais próximos de um embedding de consulta.

    Uso em pipeline:
        retriever = IRISEmbeddingRetriever(
            document_store=store,
            top_k=5
        )
    """

    def __init__(
        self,
        document_store: IRISDocumentStore,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ):
        self.document_store = document_store
        self.top_k = top_k
        self.filters = filters or {}

    @component.output_types(documents=List[Document])
    def run(
        self,
        query_embedding: List[float],
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ):
        """
        Executa a busca semântica no IRIS.

        Args:
            query_embedding : Vetor de consulta gerado pelo TextEmbedder.
            top_k           : Sobrescreve o top_k padrão do retriever.
            filters         : Filtros adicionais de metadados.

        Returns:
            {"documents": [Document, ...]}
        """
        results = self.document_store.embedding_retrieval(
            query_embedding=query_embedding,
            top_k=top_k if top_k is not None else self.top_k,
            filters={**self.filters, **(filters or {})},
        )
        return {"documents": results}

    def to_dict(self) -> Dict[str, Any]:
        return default_to_dict(
            self,
            document_store=self.document_store.to_dict(),
            top_k=self.top_k,
            filters=self.filters,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IRISEmbeddingRetriever":
        data["init_parameters"]["document_store"] = IRISDocumentStore.from_dict(
            data["init_parameters"]["document_store"]
        )
        return default_from_dict(cls, data)