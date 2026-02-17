"use client";

import { FolderOpen, Github, ClipboardPaste, ArrowRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { InputType } from "@/lib/api";

const INPUT_OPTIONS: {
  key: InputType;
  icon: React.ElementType;
  title: string;
  description: string;
}[] = [
  {
    key: "local_path",
    icon: FolderOpen,
    title: "Local Project",
    description: "Point to a folder on your machine",
  },
  {
    key: "github_url",
    icon: Github,
    title: "GitHub URL",
    description: "Paste a repository or file link",
  },
  {
    key: "pasted_code",
    icon: ClipboardPaste,
    title: "Paste Code",
    description: "Drop in a code snippet directly",
  },
];

interface WelcomeHeroProps {
  onSelect: (type: InputType) => void;
}

export default function WelcomeHero({ onSelect }: WelcomeHeroProps) {
  return (
    <div className="max-w-2xl mx-auto space-y-10 animate-fade-in">
      {/* Greeting */}
      <div className="text-center space-y-4">
        <div className="hero-glow absolute inset-0 -top-12 pointer-events-none" />
        <h1 className="relative text-4xl md:text-5xl font-extrabold tracking-tight">
          <span className="bg-gradient-to-r from-orange-400 via-amber-400 to-orange-500 bg-clip-text text-transparent">
            Phoenix Agent
          </span>
        </h1>
        <p className="text-lg text-muted-foreground leading-relaxed max-w-md mx-auto">
          I analyze your code, find smells and complexity issues, then refactor
          it — all while keeping your tests green.
        </p>
      </div>

      {/* What I can do */}
      <div className="text-center">
        <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-6">
          How would you like to get started?
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {INPUT_OPTIONS.map((opt) => (
            <Card
              key={opt.key}
              className="group cursor-pointer transition-all duration-200 hover:border-[hsl(var(--phoenix))] hover:shadow-[0_0_24px_hsl(var(--phoenix)/0.15)]"
              onClick={() => onSelect(opt.key)}
            >
              <CardContent className="p-6 text-center space-y-3">
                <div className="mx-auto w-12 h-12 rounded-xl bg-[hsl(var(--phoenix)/0.1)] flex items-center justify-center group-hover:bg-[hsl(var(--phoenix)/0.2)] transition-colors">
                  <opt.icon className="h-6 w-6 text-[hsl(var(--phoenix))]" />
                </div>
                <h3 className="font-semibold text-foreground">{opt.title}</h3>
                <p className="text-xs text-muted-foreground">
                  {opt.description}
                </p>
                <ArrowRight className="mx-auto h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Capabilities summary */}
      <div className="text-center text-xs text-muted-foreground space-y-1">
        <p>
          Observe &rarr; Reason &rarr; Plan &rarr; Decide &rarr; Act &rarr;
          Verify &rarr; Update
        </p>
        <p>7-phase autonomous refactoring with human approval for risky changes</p>
      </div>
    </div>
  );
}
