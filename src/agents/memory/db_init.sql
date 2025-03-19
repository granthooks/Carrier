-- Carrier Memory System Database Initialization
-- This script creates the necessary schema, tables, and functions for the Carrier memory system

-- Create schema function (to be called by the memory system at startup)
CREATE OR REPLACE FUNCTION public.create_memory_schema(p_schema_name text)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    -- Check if schema exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = p_schema_name) THEN
        -- Create schema
        EXECUTE format('CREATE SCHEMA %I', p_schema_name);
        
        -- Enable vector extension
        EXECUTE format('CREATE EXTENSION IF NOT EXISTS vector SCHEMA %I', p_schema_name);
        
        -- Create memories table
        EXECUTE format('
            CREATE TABLE %I.memories (
                id UUID PRIMARY KEY,
                type TEXT NOT NULL,
                content JSONB NOT NULL,
                embedding vector(1536),
                user_id TEXT NOT NULL,
                room_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                metadata JSONB DEFAULT ''{}''::jsonb,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )', p_schema_name);
            
        -- Create relationships table
        EXECUTE format('
            CREATE TABLE %I.relationships (
                id UUID PRIMARY KEY,
                user_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                interaction_count INTEGER DEFAULT 0,
                sentiment_score FLOAT,
                metadata JSONB DEFAULT ''{}''::jsonb,
                last_interaction TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )', p_schema_name);
            
        -- Create indices for common queries
        EXECUTE format('CREATE INDEX idx_memories_agent_id ON %I.memories(agent_id)', p_schema_name);
        EXECUTE format('CREATE INDEX idx_memories_user_id ON %I.memories(user_id)', p_schema_name);
        EXECUTE format('CREATE INDEX idx_memories_type ON %I.memories(type)', p_schema_name);
        EXECUTE format('CREATE INDEX idx_memories_created_at ON %I.memories(created_at)', p_schema_name);
        
        -- Create vector similarity search function
        EXECUTE format('
            CREATE OR REPLACE FUNCTION %I.match_memories(
                query_embedding vector(1536),
                match_threshold float,
                match_count int,
                schema_name text
            )
            RETURNS TABLE (
                id UUID,
                type TEXT,
                content JSONB,
                embedding vector(1536),
                user_id TEXT,
                room_id TEXT,
                agent_id TEXT,
                metadata JSONB,
                created_at TIMESTAMP WITH TIME ZONE,
                similarity float
            )
            LANGUAGE plpgsql
            AS $func$
            BEGIN
                RETURN QUERY EXECUTE format(''
                    SELECT
                        m.id,
                        m.type,
                        m.content,
                        m.embedding,
                        m.user_id,
                        m.room_id,
                        m.agent_id,
                        m.metadata,
                        m.created_at,
                        1 - (m.embedding <=> $1) as similarity
                    FROM
                        %%I.memories m
                    WHERE
                        m.embedding IS NOT NULL AND
                        1 - (m.embedding <=> $1) > $2
                    ORDER BY
                        m.embedding <=> $1
                    LIMIT $3
                '', $4)
                USING query_embedding, match_threshold, match_count;
            END;
            $func$', p_schema_name);
    END IF;
END;
$$;

-- Vector search function for the public schema
CREATE OR REPLACE FUNCTION public.match_memories(
    query_embedding vector(1536),
    match_threshold float,
    match_count int,
    schema_name text
)
RETURNS TABLE (
    id UUID,
    type TEXT,
    content JSONB,
    embedding vector(1536),
    user_id TEXT,
    room_id TEXT,
    agent_id TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY EXECUTE format('
        SELECT
            m.id,
            m.type,
            m.content,
            m.embedding,
            m.user_id,
            m.room_id,
            m.agent_id,
            m.metadata,
            m.created_at,
            1 - (m.embedding <=> $1) as similarity
        FROM
            %I.memories m
        WHERE
            m.embedding IS NOT NULL AND
            1 - (m.embedding <=> $1) > $2
        ORDER BY
            m.embedding <=> $1
        LIMIT $3
    ', schema_name)
    USING query_embedding, match_threshold, match_count;
END;
$$;
