"use client";

import { InputType } from "@/lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import FolderPicker from "./FolderPicker";

const TABS: { key: InputType; label: string }[] = [
  { key: "local_path", label: "Local Path" },
  { key: "pasted_code", label: "Paste Code" },
  { key: "github_url", label: "GitHub URL" },
];

interface InputTabsProps {
  inputType: InputType;
  onInputTypeChange: (type: InputType) => void;
  targetPath: string;
  onTargetPathChange: (v: string) => void;
  pastedCode: string;
  onPastedCodeChange: (v: string) => void;
  githubUrl: string;
  onGithubUrlChange: (v: string) => void;
}

export default function InputTabs({
  inputType,
  onInputTypeChange,
  targetPath,
  onTargetPathChange,
  pastedCode,
  onPastedCodeChange,
  githubUrl,
  onGithubUrlChange,
}: InputTabsProps) {
  return (
    <Tabs value={inputType} onValueChange={(v) => onInputTypeChange(v as InputType)}>
      <TabsList className="grid w-full grid-cols-3">
        {TABS.map((tab) => (
          <TabsTrigger key={tab.key} value={tab.key}>
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="local_path" className="pt-4">
        <div className="space-y-2">
          <Label>Project Directory</Label>
          <FolderPicker value={targetPath} onChange={onTargetPathChange} />
        </div>
      </TabsContent>
      <TabsContent value="pasted_code" className="pt-4">
        <div className="space-y-2">
          <Label htmlFor="pasted-code-input">
            Paste Your Python Code
          </Label>
          <Textarea
            id="pasted-code-input"
            value={pastedCode}
            onChange={(e) => onPastedCodeChange(e.target.value)}
            rows={12}
            placeholder="Paste your Python code here..."
            className="font-mono"
          />
        </div>
      </TabsContent>
      <TabsContent value="github_url" className="pt-4">
        <div className="space-y-2">
          <Label htmlFor="github-url-input">
            GitHub Repository URL
          </Label>
          <Input
            id="github-url-input"
            type="text"
            value={githubUrl}
            onChange={(e) => onGithubUrlChange(e.target.value)}
            placeholder="https://github.com/owner/repo"
          />
          <p className="text-xs text-muted-foreground">
            You can also link to specific branches or directories.
          </p>
        </div>
      </TabsContent>
    </Tabs>
  );
}
