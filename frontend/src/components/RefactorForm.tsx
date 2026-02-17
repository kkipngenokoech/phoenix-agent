"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { InputType, RefactorRequest, startRefactor } from "@/lib/api";
import InputTabs from "./InputTabs";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";

interface RefactorFormProps {
  defaultInputType?: InputType;
}

export default function RefactorForm({ defaultInputType = "local_path" }: RefactorFormProps) {
  const router = useRouter();
  const [inputType, setInputType] = useState<InputType>(defaultInputType);
  const [targetPath, setTargetPath] = useState("./sample_project");
  const [pastedCode, setPastedCode] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [request, setRequest] = useState(
    "Refactor UserService to follow the Single Responsibility Principle. " +
      "Extract authentication, validation, persistence, and notification into separate classes."
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const req: RefactorRequest = { input_type: inputType, request };
      if (inputType === "local_path") req.target_path = targetPath;
      else if (inputType === "pasted_code") req.pasted_code = pastedCode;
      else if (inputType === "github_url") req.github_url = githubUrl;

      const res = await startRefactor(req);
      if (res.status.startsWith("error")) {
        setError(res.status);
        return;
      }
      router.push(`/session/${res.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start refactoring");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <InputTabs
        inputType={inputType}
        onInputTypeChange={setInputType}
        targetPath={targetPath}
        onTargetPathChange={setTargetPath}
        pastedCode={pastedCode}
        onPastedCodeChange={setPastedCode}
        githubUrl={githubUrl}
        onGithubUrlChange={setGithubUrl}
      />

      <div className="space-y-2">
        <Label htmlFor="request-input">Refactoring Request</Label>
        <Textarea
          id="request-input"
          value={request}
          onChange={(e) => setRequest(e.target.value)}
          rows={4}
          placeholder="e.g., Refactor the User service to use the repository pattern..."
        />
      </div>

      {error && (
        <div className="text-sm text-destructive bg-destructive/10 rounded-lg px-4 py-3">
          <span className="font-medium">Error:</span> {error}
        </div>
      )}

      <div className="pt-2">
        <Button
          type="submit"
          disabled={loading}
          variant="phoenix"
          className="w-full"
          size="lg"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Starting Session...
            </>
          ) : (
            "Start Refactoring"
          )}
        </Button>
      </div>
    </form>
  );
}
