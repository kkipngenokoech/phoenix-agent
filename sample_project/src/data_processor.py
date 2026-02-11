"""DataProcessor - God class with too many responsibilities and high complexity."""

import csv
import json
import statistics
from datetime import datetime
from typing import Any


class DataProcessor:
    """Processes, validates, transforms, aggregates, exports, and reports on data.
    This is a God class - it does everything."""

    def __init__(self):
        self.data = []
        self.processed = []
        self.errors = []
        self.stats_cache = {}
        self.filters_applied = []
        self.transformations = []

    def load_from_csv(self, filepath):
        """Load data from CSV file."""
        try:
            with open(filepath, "r") as f:
                reader = csv.DictReader(f)
                self.data = list(reader)
            return len(self.data)
        except Exception as e:
            self.errors.append(f"CSV load error: {e}")
            return 0

    def load_from_json(self, filepath):
        """Load data from JSON file."""
        try:
            with open(filepath, "r") as f:
                self.data = json.load(f)
            return len(self.data)
        except Exception as e:
            self.errors.append(f"JSON load error: {e}")
            return 0

    def load_from_list(self, data):
        """Load data from a Python list."""
        self.data = list(data)
        return len(self.data)

    def validate_records(self, required_fields=None):
        """Validate all records have required fields."""
        required_fields = required_fields or []
        valid = []
        invalid = []
        for i, record in enumerate(self.data):
            missing = [f for f in required_fields if f not in record or record[f] is None]
            if missing:
                invalid.append({"index": i, "missing": missing, "record": record})
            else:
                valid.append(record)
        self.data = valid
        self.errors.extend([f"Record {r['index']}: missing {r['missing']}" for r in invalid])
        return {"valid": len(valid), "invalid": len(invalid)}

    def filter_by_field(self, field, value, operator="eq"):
        """Filter records by field value."""
        filtered = []
        for record in self.data:
            val = record.get(field)
            if val is None:
                continue
            if operator == "eq" and val == value:
                filtered.append(record)
            elif operator == "neq" and val != value:
                filtered.append(record)
            elif operator == "gt" and float(val) > float(value):
                filtered.append(record)
            elif operator == "lt" and float(val) < float(value):
                filtered.append(record)
            elif operator == "gte" and float(val) >= float(value):
                filtered.append(record)
            elif operator == "lte" and float(val) <= float(value):
                filtered.append(record)
            elif operator == "contains" and str(value) in str(val):
                filtered.append(record)
        self.data = filtered
        self.filters_applied.append({"field": field, "operator": operator, "value": value})
        return len(filtered)

    def transform_field(self, field, transform_type, **kwargs):
        """Apply transformation to a field across all records."""
        for record in self.data:
            if field not in record:
                continue
            val = record[field]
            if transform_type == "uppercase":
                record[field] = str(val).upper()
            elif transform_type == "lowercase":
                record[field] = str(val).lower()
            elif transform_type == "strip":
                record[field] = str(val).strip()
            elif transform_type == "to_int":
                try:
                    record[field] = int(float(val))
                except (ValueError, TypeError):
                    record[field] = 0
            elif transform_type == "to_float":
                try:
                    record[field] = float(val)
                except (ValueError, TypeError):
                    record[field] = 0.0
            elif transform_type == "prefix":
                record[field] = kwargs.get("prefix", "") + str(val)
            elif transform_type == "suffix":
                record[field] = str(val) + kwargs.get("suffix", "")
            elif transform_type == "replace":
                record[field] = str(val).replace(
                    kwargs.get("old", ""), kwargs.get("new", "")
                )
        self.transformations.append({"field": field, "type": transform_type})
        return len(self.data)

    def calculate_stats(self, field):
        """Calculate statistics for a numeric field."""
        values = []
        for record in self.data:
            try:
                values.append(float(record.get(field, 0)))
            except (ValueError, TypeError):
                continue

        if not values:
            return {"error": "No numeric values found"}

        result = {
            "count": len(values),
            "sum": sum(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "range": max(values) - min(values),
        }
        if len(values) > 1:
            result["stdev"] = statistics.stdev(values)
            result["variance"] = statistics.variance(values)

        self.stats_cache[field] = result
        return result

    def group_by(self, field):
        """Group records by a field value."""
        groups = {}
        for record in self.data:
            key = record.get(field, "unknown")
            if key not in groups:
                groups[key] = []
            groups[key].append(record)
        return groups

    def sort_records(self, field, reverse=False):
        """Sort records by field."""
        try:
            self.data.sort(key=lambda r: r.get(field, ""), reverse=reverse)
        except TypeError:
            self.data.sort(key=lambda r: str(r.get(field, "")), reverse=reverse)
        return len(self.data)

    def deduplicate(self, key_field):
        """Remove duplicate records based on a key field."""
        seen = set()
        unique = []
        for record in self.data:
            key = record.get(key_field)
            if key not in seen:
                seen.add(key)
                unique.append(record)
        removed = len(self.data) - len(unique)
        self.data = unique
        return {"kept": len(unique), "removed": removed}

    def export_to_csv(self, filepath):
        """Export data to CSV."""
        if not self.data:
            return False
        try:
            with open(filepath, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.data[0].keys())
                writer.writeheader()
                writer.writerows(self.data)
            return True
        except Exception as e:
            self.errors.append(f"CSV export error: {e}")
            return False

    def export_to_json(self, filepath):
        """Export data to JSON."""
        try:
            with open(filepath, "w") as f:
                json.dump(self.data, f, indent=2, default=str)
            return True
        except Exception as e:
            self.errors.append(f"JSON export error: {e}")
            return False

    def generate_report(self, title="Data Report", numeric_fields=None):
        """Generate a text report of the data."""
        lines = [
            f"{'='*60}",
            f"  {title}",
            f"  Generated: {datetime.now().isoformat()}",
            f"{'='*60}",
            f"",
            f"Records: {len(self.data)}",
            f"Errors: {len(self.errors)}",
            f"Filters applied: {len(self.filters_applied)}",
            f"Transformations: {len(self.transformations)}",
        ]

        if numeric_fields:
            lines.append(f"\nStatistics:")
            for field in numeric_fields:
                stats = self.calculate_stats(field)
                if "error" not in stats:
                    lines.append(f"\n  {field}:")
                    lines.append(f"    Count: {stats['count']}")
                    lines.append(f"    Mean: {stats['mean']:.2f}")
                    lines.append(f"    Median: {stats['median']:.2f}")
                    lines.append(f"    Min: {stats['min']:.2f}")
                    lines.append(f"    Max: {stats['max']:.2f}")

        return "\n".join(lines)

    def get_errors(self):
        """Return all accumulated errors."""
        return list(self.errors)

    def clear(self):
        """Reset all data and state."""
        self.data = []
        self.processed = []
        self.errors = []
        self.stats_cache = {}
        self.filters_applied = []
        self.transformations = []
