"""Tests for DataProcessor."""

import pytest
from src.data_processor import DataProcessor


@pytest.fixture
def processor():
    return DataProcessor()


@pytest.fixture
def sample_data():
    return [
        {"name": "Alice", "age": "30", "score": "85", "dept": "engineering"},
        {"name": "Bob", "age": "25", "score": "92", "dept": "engineering"},
        {"name": "Carol", "age": "35", "score": "78", "dept": "marketing"},
        {"name": "Dave", "age": "28", "score": "95", "dept": "marketing"},
        {"name": "Eve", "age": "32", "score": "88", "dept": "engineering"},
    ]


class TestLoading:
    def test_load_from_list(self, processor, sample_data):
        count = processor.load_from_list(sample_data)
        assert count == 5

    def test_load_empty_list(self, processor):
        count = processor.load_from_list([])
        assert count == 0


class TestValidation:
    def test_validate_with_required_fields(self, processor, sample_data):
        processor.load_from_list(sample_data)
        result = processor.validate_records(required_fields=["name", "age"])
        assert result["valid"] == 5
        assert result["invalid"] == 0

    def test_validate_with_missing_field(self, processor):
        data = [{"name": "Alice"}, {"name": "Bob", "email": "bob@test.com"}]
        processor.load_from_list(data)
        result = processor.validate_records(required_fields=["name", "email"])
        assert result["valid"] == 1
        assert result["invalid"] == 1


class TestFiltering:
    def test_filter_eq(self, processor, sample_data):
        processor.load_from_list(sample_data)
        count = processor.filter_by_field("dept", "engineering")
        assert count == 3

    def test_filter_gt(self, processor, sample_data):
        processor.load_from_list(sample_data)
        count = processor.filter_by_field("score", 90, operator="gt")
        assert count == 2


class TestTransformation:
    def test_uppercase(self, processor, sample_data):
        processor.load_from_list(sample_data)
        processor.transform_field("name", "uppercase")
        assert processor.data[0]["name"] == "ALICE"

    def test_to_int(self, processor, sample_data):
        processor.load_from_list(sample_data)
        processor.transform_field("age", "to_int")
        assert processor.data[0]["age"] == 30


class TestStatistics:
    def test_calculate_stats(self, processor, sample_data):
        processor.load_from_list(sample_data)
        stats = processor.calculate_stats("score")
        assert stats["count"] == 5
        assert stats["min"] == 78.0
        assert stats["max"] == 95.0


class TestGrouping:
    def test_group_by(self, processor, sample_data):
        processor.load_from_list(sample_data)
        groups = processor.group_by("dept")
        assert len(groups["engineering"]) == 3
        assert len(groups["marketing"]) == 2


class TestDeduplication:
    def test_deduplicate(self, processor):
        data = [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
            {"id": "1", "name": "Alice Dup"},
        ]
        processor.load_from_list(data)
        result = processor.deduplicate("id")
        assert result["kept"] == 2
        assert result["removed"] == 1
