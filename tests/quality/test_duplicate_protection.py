"""Tests for duplicate panel protection service."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from bb_paxdata.domain.services.duplicate_protection import DuplicateProtectionService
from bb_paxdata.infrastructure.db.processed_files import ProcessedFile


class TestDuplicateProtectionService:
    """Test cases for DuplicateProtectionService."""

    @pytest.fixture
    def mock_db_session(self) -> Mock:
        """Create mock database session."""
        return Mock()

    @pytest.fixture
    def service(self, mock_db_session: Mock) -> DuplicateProtectionService:
        """Create DuplicateProtectionService instance."""
        return DuplicateProtectionService(mock_db_session)

    @pytest.fixture
    def sample_file_content(self) -> str:
        """Sample file content for testing."""
        return "Sample transcript content for testing purposes."

    @pytest.fixture
    def sample_file_path(self) -> Path:
        """Sample file path for testing."""
        return Path("test_transcript.txt")

    def test_generate_idempotency_key(
        self,
        service: DuplicateProtectionService,
        sample_file_content: str,
        sample_file_path: Path,
    ) -> None:
        """Test idempotency key generation."""
        key = service.generate_idempotency_key(
            sample_file_content, str(sample_file_path), "1.0", "1.0"
        )

        # Should be a SHA256 hash (64 characters)
        assert len(key) == 64
        assert isinstance(key, str)

        # Same input should generate same key
        key2 = service.generate_idempotency_key(
            sample_file_content, str(sample_file_path), "1.0", "1.0"
        )
        assert key == key2

        # Different version should generate different key
        key3 = service.generate_idempotency_key(
            sample_file_content, str(sample_file_path), "2.0", "1.0"
        )
        assert key != key3

    def test_is_already_processed_new_file(
        self, service: DuplicateProtectionService, mock_db_session: Mock
    ) -> None:
        """Test checking new file processing status."""
        # Mock database query to return None (not processed)
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        is_processed, processed_file = service.is_already_processed("test_key")

        assert is_processed is False
        assert processed_file is None

    def test_is_already_processed_existing_file(
        self, service: DuplicateProtectionService, mock_db_session: Mock
    ) -> None:
        """Test checking existing file processing status."""
        # Create mock processed file
        mock_processed_file = ProcessedFile(
            file_hash="abc123",
            file_name="test.txt",
            file_size_bytes=100,
            idempotency_key="test_key",
            force_rebuild=0,
        )

        # Mock database query to return processed file
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_processed_file
        )

        is_processed, processed_file = service.is_already_processed("test_key")

        assert is_processed is True
        assert processed_file == mock_processed_file

    def test_is_already_processed_force_rebuild(
        self, service: DuplicateProtectionService, mock_db_session: Mock
    ) -> None:
        """Test force rebuild bypasses duplicate check."""
        is_processed, processed_file = service.is_already_processed(
            "test_key", force_rebuild=True
        )

        assert is_processed is False
        assert processed_file is None

    @patch("bb_paxdata.domain.services.duplicate_protection.hashlib.sha256")
    def test_mark_as_processed_new(
        self,
        mock_sha256: Mock,
        service: DuplicateProtectionService,
        mock_db_session: Mock,
        sample_file_path: Path,
        sample_file_content: str,
    ) -> None:
        """Test marking new file as processed."""
        # Mock SHA256
        mock_hash = Mock()
        mock_hash.hexdigest.return_value = "mock_hash_value"
        mock_sha256.return_value = mock_hash

        # Mock database operations
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()

        idempotency_key = "test_key"
        result = service.mark_as_processed(
            sample_file_path, sample_file_content, idempotency_key
        )

        assert result is not None
        assert result.file_name == sample_file_path.name
        assert result.idempotency_key == idempotency_key
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @patch("bb_paxdata.domain.services.duplicate_protection.hashlib.sha256")
    def test_mark_as_processed_existing(
        self,
        mock_sha256: Mock,
        service: DuplicateProtectionService,
        mock_db_session: Mock,
        sample_file_path: Path,
        sample_file_content: str,
    ) -> None:
        """Test updating existing processed file record."""
        # Mock SHA256
        mock_hash = Mock()
        mock_hash.hexdigest.return_value = "mock_hash_value"
        mock_sha256.return_value = mock_hash

        # Create existing processed file
        existing_file = ProcessedFile(
            file_hash="abc123",
            file_name="test.txt",
            file_size_bytes=100,
            idempotency_key="test_key",
            reprocess_count=1,
        )

        # Mock database operations
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            existing_file
        )
        mock_db_session.commit = Mock()

        idempotency_key = "test_key"
        result = service.mark_as_processed(
            sample_file_path, sample_file_content, idempotency_key
        )

        assert result == existing_file
        assert result.reprocess_count == 2  # Should be incremented
        mock_db_session.commit.assert_called_once()

    def test_get_existing_panel_found(
        self, service: DuplicateProtectionService, mock_db_session: Mock
    ) -> None:
        """Test getting existing panel."""
        # Mock processed file
        processed_file = ProcessedFile(
            file_hash="abc123",
            file_name="test.txt",
            file_size_bytes=100,
            idempotency_key="test_key",
        )

        # Mock panel
        mock_panel = Mock()
        mock_panel.panel_id = "test_panel_id"
        mock_panel.is_active = 1

        # Mock database queries
        mock_db_session.query.return_value.filter.side_effect = [
            Mock(
                first=Mock(return_value=processed_file)
            ),  # First query for ProcessedFile
            Mock(first=Mock(return_value=mock_panel)),  # Second query for Panel
        ]

        result = service.get_existing_panel(Path("test.txt"), "content", "test_key")

        assert result == mock_panel

    def test_get_existing_panel_not_found(
        self, service: DuplicateProtectionService, mock_db_session: Mock
    ) -> None:
        """Test getting non-existing panel."""
        # Mock database queries to return None
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        result = service.get_existing_panel(Path("test.txt"), "content", "test_key")

        assert result is None

    def test_soft_delete_existing_panel(
        self, service: DuplicateProtectionService, mock_db_session: Mock
    ) -> None:
        """Test soft deleting existing panels."""
        # Mock processed file
        processed_file = ProcessedFile(
            file_hash="abc123",
            file_name="test.txt",
            file_size_bytes=100,
            idempotency_key="test_key",
        )

        # Mock panels
        mock_panel1 = Mock()
        mock_panel1.is_active = 1
        mock_panel2 = Mock()
        mock_panel2.is_active = 1

        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            processed_file
        )
        mock_db_session.query.return_value.filter.return_value.all.return_value = [
            mock_panel1,
            mock_panel2,
        ]
        mock_db_session.commit = Mock()

        result = service.soft_delete_existing_panel(
            Path("test.txt"), "content", "test_key"
        )

        assert result is True
        assert mock_panel1.is_active == 0
        assert mock_panel2.is_active == 0
        mock_db_session.commit.assert_called_once()

    def test_mark_force_rebuild(
        self, service: DuplicateProtectionService, mock_db_session: Mock
    ) -> None:
        """Test marking file for force rebuild."""
        # Mock processed file
        processed_file = ProcessedFile(
            file_hash="abc123",
            file_name="test.txt",
            file_size_bytes=100,
            idempotency_key="test_key",
            force_rebuild=0,
        )

        # Mock database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            processed_file
        )
        mock_db_session.commit = Mock()

        result = service.mark_force_rebuild(Path("test.txt"), "content", "test_key")

        assert result is True
        assert processed_file.force_rebuild == 1
        mock_db_session.commit.assert_called_once()

    def test_get_processing_statistics(
        self, service: DuplicateProtectionService, mock_db_session: Mock
    ) -> None:
        """Test getting processing statistics."""
        # Mock database queries
        mock_db_session.query.return_value.count.return_value = 10
        mock_db_session.query.return_value.filter.return_value.count.return_value = 3
        mock_query = mock_db_session.query.return_value
        mock_query.order_by.return_value.limit.return_value.all.return_value = []

        # Mock avg query
        with patch(
            "bb_paxdata.domain.services.duplicate_protection.func.avg"
        ) as mock_avg:
            mock_avg.return_value.scalar.return_value = 2.5

            stats = service.get_processing_statistics()

            assert stats["total_processed_files"] == 10
            assert stats["force_rebuild_count"] == 3
            assert stats["average_reprocess_count"] == 2.5
            assert isinstance(stats["most_processed_files"], list)

    def test_cleanup_old_records(
        self, service: DuplicateProtectionService, mock_db_session: Mock
    ) -> None:
        """Test cleaning up old records."""
        result = service.cleanup_old_records(days_to_keep=90)

        # Should return 0 for now (placeholder implementation)
        assert result == 0
