"use client";

import { useState, useEffect } from "react";
import { browseFolders, BrowseResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  FolderOpen,
  FolderClosed,
  ChevronRight,
  ChevronUp,
  Check,
  Loader2,
} from "lucide-react";

interface FolderPickerProps {
  value: string;
  onChange: (path: string) => void;
}

export default function FolderPicker({ value, onChange }: FolderPickerProps) {
  const [open, setOpen] = useState(false);
  const [browseResult, setBrowseResult] = useState<BrowseResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const browse = async (path?: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await browseFolders(path);
      if (result.error) {
        setError(result.error);
      } else {
        setBrowseResult(result);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to browse");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && !browseResult) {
      browse(value || "~");
    }
  }, [open]);

  const handleSelect = () => {
    if (browseResult) {
      onChange(browseResult.current);
      setOpen(false);
    }
  };

  const handleNavigate = (path: string) => {
    browse(path);
  };

  // Breadcrumb segments from current path
  const breadcrumbs = browseResult
    ? browseResult.current.split("/").filter(Boolean)
    : [];

  return (
    <div className="space-y-2">
      {/* Selected path display + browse button */}
      <div className="flex gap-2">
        <div
          className="flex-1 flex items-center gap-2 px-3 py-2 rounded-md border border-input bg-background text-sm cursor-pointer hover:border-[hsl(var(--phoenix)/0.5)] transition-colors"
          onClick={() => setOpen(!open)}
        >
          <FolderOpen className="h-4 w-4 text-[hsl(var(--phoenix))] shrink-0" />
          <span className={value ? "text-foreground" : "text-muted-foreground"}>
            {value || "Select a project folder..."}
          </span>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={() => {
            setOpen(!open);
            if (!open) browse(value || "~");
          }}
        >
          Browse
        </Button>
      </div>

      {/* Folder browser panel */}
      {open && (
        <div className="border border-border rounded-lg bg-card overflow-hidden animate-fade-in">
          {/* Breadcrumb */}
          {browseResult && (
            <div className="flex items-center gap-1 px-3 py-2 bg-muted/50 border-b border-border text-xs text-muted-foreground overflow-x-auto">
              <button
                className="hover:text-foreground transition-colors"
                onClick={() => handleNavigate("/")}
              >
                /
              </button>
              {breadcrumbs.map((segment, i) => {
                const fullPath = "/" + breadcrumbs.slice(0, i + 1).join("/");
                return (
                  <span key={fullPath} className="flex items-center gap-1">
                    <ChevronRight className="h-3 w-3" />
                    <button
                      className="hover:text-foreground transition-colors"
                      onClick={() => handleNavigate(fullPath)}
                    >
                      {segment}
                    </button>
                  </span>
                );
              })}
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center py-6 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              Loading...
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="px-3 py-4 text-sm text-destructive">{error}</div>
          )}

          {/* Directory listing */}
          {browseResult && !loading && (
            <div className="max-h-60 overflow-y-auto">
              {/* Go up */}
              {browseResult.parent && (
                <button
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:bg-muted/50 transition-colors"
                  onClick={() => handleNavigate(browseResult.parent!)}
                >
                  <ChevronUp className="h-4 w-4" />
                  ..
                </button>
              )}

              {browseResult.entries.length === 0 && (
                <div className="px-3 py-4 text-sm text-muted-foreground text-center">
                  No subdirectories
                </div>
              )}

              {browseResult.entries.map((entry) => (
                <button
                  key={entry.path}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted/50 transition-colors text-left"
                  onClick={() => handleNavigate(entry.path)}
                >
                  {entry.has_children ? (
                    <FolderClosed className="h-4 w-4 text-[hsl(var(--phoenix))]" />
                  ) : (
                    <FolderClosed className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span className="text-foreground">{entry.name}</span>
                  {entry.has_children && (
                    <ChevronRight className="h-3 w-3 text-muted-foreground ml-auto" />
                  )}
                </button>
              ))}
            </div>
          )}

          {/* Select button */}
          {browseResult && !loading && (
            <div className="flex items-center justify-between px-3 py-2 border-t border-border bg-muted/30">
              <span className="text-xs text-muted-foreground truncate mr-2">
                {browseResult.current}
              </span>
              <Button
                type="button"
                size="sm"
                variant="phoenix"
                className="shrink-0 gap-1"
                onClick={handleSelect}
              >
                <Check className="h-3 w-3" />
                Select
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
