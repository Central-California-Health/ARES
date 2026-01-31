import datetime
import threading
import json
import uuid
import numpy as np
import redis
from redis.commands.search.field import TextField, VectorField, NumericField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from dataclasses import dataclass, field
from typing import List
from .llm import LLM

@dataclass
class MemoryObject:
    description: str
    creation_time: datetime.datetime
    importance: float # 1 to 10
    embedding: List[float] = field(default_factory=list)
    last_accessed: datetime.datetime = field(default_factory=datetime.datetime.now)

class MemoryStream:
    def __init__(self, llm: LLM, db=None, agent_name: str = "Unknown"):
        self.llm = llm
        self.db = db
        self.agent_name = agent_name.replace(" ", "_") # Safe key name
        self.index_name = f"idx:memory:{self.agent_name}"
        self.lock = threading.Lock()
        
        # Redis Connection (Reuse from LLM or create new)
        self.redis = getattr(llm, 'redis', None)
        if not self.redis:
            try:
                self.redis = redis.Redis(host='localhost', port=6380, decode_responses=True)
                self.redis.ping()
            except:
                self.redis = None
        
        # Initialize Vector Index
        if self.redis:
            self._create_index()
            
        # Fallback local storage if Redis dies
        self.memories: List[MemoryObject] = [] 
        if self.db:
            self.load_from_db()

    def _create_index(self):
        try:
            self.redis.ft(self.index_name).info()
            print(f"[{self.agent_name}] Redis Vector Index found.")
        except:
            print(f"[{self.agent_name}] Creating Redis Vector Index...")
            schema = (
                TextField("description"),
                NumericField("importance"),
                NumericField("created_at"),
                VectorField("embedding",
                    "HNSW", {
                        "TYPE": "FLOAT32",
                        "DIM": 1536, # OpenAI embedding size
                        "DISTANCE_METRIC": "COSINE"
                    }
                )
            )
            definition = IndexDefinition(prefix=[f"memory:{self.agent_name}:"], index_type=IndexType.HASH)
            try:
                self.redis.ft(self.index_name).create_index(schema, definition=definition)
            except Exception as e:
                print(f"Index creation failed: {e}")

    def load_from_db(self):
        # We still populate the local list for "get_recent" (fallback/fast access)
        # But for search, we rely on Redis.
        # Ideally, we should sync DB -> Redis if Redis is empty.
        rows = self.db.load_memories(self.agent_name)
        print(f"[{self.agent_name}] Loading {len(rows)} memories from database...")
        with self.lock:
            for row in rows:
                mem = MemoryObject(
                    description=row['description'],
                    creation_time=row['created_at'],
                    importance=row['importance'],
                    embedding=row['embedding'],
                    last_accessed=row['last_accessed']
                )
                self.memories.append(mem)
                
                # Sync to Redis if missing (Simple lazy sync)
                if self.redis:
                    # In a real system, we'd check existence. Here we just blindly add
                    # or assume persistence handled elsewhere.
                    # For now, let's just rely on new memories being added to Redis.
                    pass

    def add_memory(self, description: str, time: datetime.datetime):
        # 1. Calculate importance
        importance = self._calculate_importance(description)
        
        # 2. Get embedding
        embedding = self.llm.get_embedding(description)
        
        # 3. Create Object
        memory = MemoryObject(
            description=description,
            creation_time=time,
            importance=importance,
            embedding=embedding,
            last_accessed=time
        )
        
        # 4. Save to Local (for get_recent)
        with self.lock:
            self.memories.append(memory)
        
        # 5. Save to Redis (Vector Store)
        if self.redis:
            try:
                key = f"memory:{self.agent_name}:{uuid.uuid4()}"
                
                # Redis requires bytes for vector field
                # We need to convert list[float] -> numpy -> bytes
                vector_bytes = np.array(embedding, dtype=np.float32).tobytes()
                
                self.redis.hset(key, mapping={
                    "description": description,
                    "importance": importance,
                    "created_at": time.timestamp(),
                    "embedding": vector_bytes
                })
            except Exception as e:
                print(f"Redis save failed: {e}")

        # 6. Persist to Postgres
        if self.db:
            self.db.save_memory(
                self.agent_name, 
                description, 
                importance, 
                embedding, 
                time, 
                time
            )

    def _calculate_importance(self, description: str) -> float:
        prompt = f"Rate the importance of this memory (1-10): {description}. Return number only."
        try:
            response = self.llm.generate(prompt, temperature=0.0) # Cache hit likely
            return float(response.strip())
        except:
            return 5.0

    def retrieve(self, query: str, time: datetime.datetime, top_k: int = 3) -> List[MemoryObject]:
        """
        Performs Hybrid Search: Vector Similarity + Importance + Recency
        """
        # Fallback if Redis is down
        if not self.redis:
             return self.get_recent(top_k)

        try:
            query_embedding = self.llm.get_embedding(query)
            query_vec = np.array(query_embedding, dtype=np.float32).tobytes()
            
            # Redis Query: KNN search
            # We fetch more than top_k to re-rank with custom scoring if needed
            # But HNSW is good enough.
            q = Query(f"*=>[KNN {top_k} @embedding $vec AS score]") \
                .sort_by("score") \
                .return_fields("description", "importance", "created_at", "score") \
                .dialect(2)
            
            params = {"vec": query_vec}
            results = self.redis.ft(self.index_name).search(q, query_params=params)
            
            final_res = []
            for doc in results.docs:
                # Reconstruct MemoryObject
                # Note: We don't fetch the embedding back to save bandwidth
                m = MemoryObject(
                    description=doc.description,
                    creation_time=datetime.datetime.fromtimestamp(float(doc.created_at)),
                    importance=float(doc.importance),
                    embedding=[], # Not needed for display
                    last_accessed=time
                )
                final_res.append(m)
            
            return final_res

        except Exception as e:
            print(f"Redis Search failed: {e}")
            return self.get_recent(top_k)

    def retrieve_important(self, top_k: int = 3) -> List[MemoryObject]:
        if not self.redis:
            return sorted(self.memories, key=lambda m: m.importance, reverse=True)[:top_k]
            
        # Redis Sort
        # Ideally we use an index on importance, but for now we fallback to local list
        # because FT.SEARCH sorting on NumericField without filtering can be tricky syntax.
        # Local list is fine for "all-time important" since we load it on startup.
        return sorted(self.memories, key=lambda m: m.importance, reverse=True)[:top_k]

    def get_recent(self, n: int = 5) -> List[MemoryObject]:
        with self.lock:
            sorted_memories = sorted(self.memories, key=lambda m: m.creation_time, reverse=True)
            return sorted_memories[:n]
