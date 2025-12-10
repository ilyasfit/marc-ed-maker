import os
import json
import hashlib
import logging
from typing import List, Dict, Optional
import chromadb
from chromadb.utils import embedding_functions
from shared import config

logger = logging.getLogger(__name__)

class EmbeddingManager:
    def __init__(self, 
                 chroma_db_path: str = None, 
                 qna_context_path: str = None, 
                 state_file_path: str = None):
        
        self.chroma_db_path = chroma_db_path or os.path.join(os.path.dirname(__file__), 'chroma_db')
        self.qna_context_path = qna_context_path or config.QNA_CONTEXT_PATH
        self.vectorize_path = os.path.join(self.qna_context_path, 'vectorize')
        self.state_file_path = state_file_path or os.path.join(os.path.dirname(__file__), 'state', 'embedding_state.json')
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=self.chroma_db_path)
        
        # Configure Embedding Function
        if config.OPENAI_API_KEY:
            self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=config.OPENAI_API_KEY,
                model_name="text-embedding-3-small"
            )
        else:
            logger.warning("No OpenAI API Key found. Vector store will not function correctly for new embeddings.")
            self.embedding_fn = None

        self.collection = self.chroma_client.get_or_create_collection(
            name="qna_context",
            embedding_function=self.embedding_fn
        )
        self.state = self.load_state()

    def load_state(self) -> Dict[str, str]:
        if os.path.exists(self.state_file_path):
            try:
                with open(self.state_file_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state file: {e}")
                return {}
        return {}

    def save_state(self):
        os.makedirs(os.path.dirname(self.state_file_path), exist_ok=True)
        with open(self.state_file_path, 'w') as f:
            json.dump(self.state, f, indent=2)

    def calculate_file_hash(self, filepath: str) -> str:
        sha256_hash = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error hashing file {filepath}: {e}")
            return ""

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        if not text:
            return []
            
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + chunk_size
            if end >= text_len:
                chunks.append(text[start:])
                break
            
            # Simple intelligent splitting priority: \n\n > \n > . > space
            next_break = -1
            for separator in ['\n\n', '\n', '. ', ' ']:
                idx = text.rfind(separator, start, end)
                if idx > start:
                    next_break = idx
                    break
            
            if next_break == -1:
                next_break = end

            chunks.append(text[start:next_break].strip())
            
            # Update start for next chunk
            prev_start = start
            start = next_break + 1 - overlap
            if start < 0: start = 0
            
            # Prevent infinite loops: ensure we always verify forward progress
            if start <= prev_start:
                 start = next_break + 1
                 
        return [c for c in chunks if c.strip()]

    def sync_knowledge_base(self):
        """
        Synchronizes the vector store with the files in the 'vectorize' subdirectory of QNA_CONTEXT_PATH.
        """
        logger.info(f"Starting knowledge base synchronization from {self.vectorize_path}...")
        
        if not os.path.exists(self.vectorize_path):
             logger.warning(f"Vectorize directory not found: {self.vectorize_path}")
             os.makedirs(self.vectorize_path, exist_ok=True)
             
        current_files = []
        for root, _, files in os.walk(self.vectorize_path):
            for file in sorted(files):
                if file.endswith(('.md', '.txt')):
                    current_files.append(os.path.join(root, file))

        current_file_map = {f: self.calculate_file_hash(f) for f in current_files}
        
        # Identify deleted files
        known_files = set(self.state.keys())
        current_files_set = set(current_file_map.keys())
        deleted_files = known_files - current_files_set
        
        changes_made = False

        for file in deleted_files:
            logger.info(f"Removing deleted file from vector store: {file}")
            try:
                self.collection.delete(where={"source": file})
                del self.state[file]
                changes_made = True
            except Exception as e:
                logger.error(f"Error removing file {file}: {e}")

        # Identify new or changed files
        for file, file_hash in current_file_map.items():
            if file not in self.state or self.state[file] != file_hash:
                status = "New" if file not in self.state else "Changed"
                logger.info(f"Processing {status} file: {file}")
                
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # If changed, remove old chunks first
                    if status == "Changed":
                         self.collection.delete(where={"source": file})

                    chunks = self.chunk_text(content)
                    if chunks:
                        ids = [f"{file}_{i}_{file_hash[:8]}" for i in range(len(chunks))]
                        metadatas = [{"source": file, "chunk_index": i} for i in range(len(chunks))]
                        
                        self.collection.add(
                            documents=chunks,
                            ids=ids,
                            metadatas=metadatas
                        )
                    
                    self.state[file] = file_hash
                    changes_made = True
                except Exception as e:
                    logger.error(f"Error processing file {file}: {e}")

        if changes_made:
            self.save_state()
            logger.info("Knowledge base synchronization complete.")
        else:
            logger.info("Knowledge base is up to date.")

    def query_context(self, query: str, n_results: int = 5) -> str:
        """
        Retrieves relevant context for a query.
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            if not results['documents']:
                return ""
            
            # Flatten the list of lists
            docs = results['documents'][0]
            metadatas = results['metadatas'][0]
            
            # Add retrieval logging/metadata info if needed, or structured output.
            # For now just join them, but optionally we could prefix the source file.
            formatted_docs = []
            for doc, meta in zip(docs, metadatas):
                source = meta.get('source', 'Unknown Source')
                formatted_docs.append(f"Source: {source}\nContent:\n{doc}")

            return "\n\n---\n\n".join(formatted_docs)
        except Exception as e:
            logger.error(f"Error querying vector store: {e}")
            return ""
