import asyncio
import uuid
import httpx
from sqlalchemy import text, select
from sqlalchemy.orm import selectinload

from app.main import app
from app.core.database import async_engine, AsyncSessionLocal
from app.models import User, Document, DocumentChunk, Conversation, Message


def test_database_connection_and_pgvector():
    """Verify asynchronous database connection and pgvector extension."""
    async def _test():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
            )
            row = result.fetchone()
            assert row is not None, "pgvector extension is not installed"
            assert row[0] == "vector"
            assert row[1] is not None

    asyncio.run(_test())


def test_all_expected_tables_exist():
    """Verify all 5 application tables and Alembic version table exist."""
    async def _test():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public';
                """)
            )
            tables = {r[0] for r in result.fetchall()}
            expected_tables = {
                "users",
                "documents",
                "document_chunks",
                "conversations",
                "messages",
                "alembic_version",
            }
            for expected in expected_tables:
                assert expected in tables, f"Expected table '{expected}' not found in database"

    asyncio.run(_test())


def test_models_crud_and_relationships():
    """Verify full CRUD, foreign keys, relationships, and vector column."""
    async def _test():
        async with AsyncSessionLocal() as session:
            # 1. Create User
            test_email = f"test_{uuid.uuid4().hex[:8]}@cogniva.ai"
            user = User(
                email=test_email,
                full_name="Phase 2 Integration User",
                hashed_password="placeholder_hash",
            )
            session.add(user)
            await session.flush()
            assert user.id is not None

            # 2. Create Document linked to User
            doc = Document(
                user_id=user.id,
                filename="enterprise_manual.pdf",
                original_filename="Enterprise Manual.pdf",
                file_type="pdf",
                storage_path="/data/enterprise_manual.pdf",
                status="processed",
                metadata_={"department": "Security", "classification": "Confidential"},
            )
            session.add(doc)
            await session.flush()
            assert doc.id is not None

            # 3. Create DocumentChunk with 1536-dim embedding linked to Document
            dummy_embedding = [0.05] * 1536
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=0,
                content="Cogniva securely stores and retrieves multimodal embeddings.",
                page_number=1,
                metadata_={"heading": "Overview"},
                embedding=dummy_embedding,
            )
            session.add(chunk)
            await session.flush()
            assert chunk.id is not None

            # 4. Create Conversation linked to User
            conversation = Conversation(
                user_id=user.id,
                title="Q&A Session",
            )
            session.add(conversation)
            await session.flush()
            assert conversation.id is not None

            # 5. Create Message linked to Conversation
            message = Message(
                conversation_id=conversation.id,
                role="user",
                content="Can you summarize the security guidelines?",
                metadata_={"timestamp_utc": "2026-10-08T00:00:00Z"},
            )
            session.add(message)
            await session.flush()
            assert message.id is not None

            # 6. Query and assert relationships
            stmt = (
                select(User)
                .options(
                    selectinload(User.documents).selectinload(Document.chunks),
                    selectinload(User.conversations).selectinload(Conversation.messages),
                )
                .where(User.id == user.id)
            )
            res = await session.execute(stmt)
            loaded_user = res.scalar_one()

            assert loaded_user.email == test_email
            assert len(loaded_user.documents) == 1
            assert loaded_user.documents[0].filename == "enterprise_manual.pdf"
            assert len(loaded_user.documents[0].chunks) == 1
            assert len(loaded_user.documents[0].chunks[0].embedding) == 1536
            assert len(loaded_user.conversations) == 1
            assert len(loaded_user.conversations[0].messages) == 1
            assert loaded_user.conversations[0].messages[0].role == "user"

            # Rollback clean up
            await session.rollback()

    asyncio.run(_test())


def test_fastapi_health_endpoint():
    """Verify FastAPI application starts and /api/v1/health returns 200 ok."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert data.get("status") == "ok"
            assert data.get("app") == "Cogniva"

    asyncio.run(_test())
