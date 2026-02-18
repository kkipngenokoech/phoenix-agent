-- Add original and refactored file contents to history
ALTER TABLE refactoring_history ADD COLUMN IF NOT EXISTS original_files JSONB DEFAULT '{}'::jsonb;
ALTER TABLE refactoring_history ADD COLUMN IF NOT EXISTS refactored_files JSONB DEFAULT '{}'::jsonb;
