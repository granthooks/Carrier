-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the carrier_memory schema
CREATE SCHEMA IF NOT EXISTS carrier_memory;

-- Create memories table
CREATE TABLE IF NOT EXISTS carrier_memory.memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT,
    user_id TEXT,
    room_id TEXT,
    type TEXT NOT NULL,
    content JSONB NOT NULL,
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index on agent_id, user_id, room_id, and type
CREATE INDEX IF NOT EXISTS memories_agent_id_idx ON carrier_memory.memories (agent_id);
CREATE INDEX IF NOT EXISTS memories_user_id_idx ON carrier_memory.memories (user_id);
CREATE INDEX IF NOT EXISTS memories_room_id_idx ON carrier_memory.memories (room_id);
CREATE INDEX IF NOT EXISTS memories_type_idx ON carrier_memory.memories (type);

-- Create vector index for similarity search (only if pgvector extension is available)
CREATE INDEX IF NOT EXISTS memories_embedding_idx ON carrier_memory.memories 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);