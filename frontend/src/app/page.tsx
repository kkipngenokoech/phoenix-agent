"use client";

import { useState } from "react";
import { InputType } from "@/lib/api";
import WelcomeHero from "@/components/WelcomeHero";
import RefactorForm from "@/components/RefactorForm";
import AnalysisView from "@/components/AnalysisView";
import Layout from "@/components/Layout";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Sparkles, Search, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState("refactor");
  const [selectedInput, setSelectedInput] = useState<InputType | null>(null);

  // Welcome screen — user hasn't picked an input method yet
  if (!selectedInput) {
    return (
      <Layout>
        <div className="py-8">
          <WelcomeHero onSelect={setSelectedInput} />
        </div>
      </Layout>
    );
  }

  // Main workspace — user has chosen how to provide code
  return (
    <Layout>
      <div className="space-y-6 animate-fade-in">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setSelectedInput(null)}
          className="text-muted-foreground hover:text-foreground gap-1"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>

        <div className="max-w-3xl mx-auto">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-2 mb-6">
              <TabsTrigger value="refactor" className="gap-2">
                <Sparkles className="h-4 w-4" />
                Refactor
              </TabsTrigger>
              <TabsTrigger value="analyze" className="gap-2">
                <Search className="h-4 w-4" />
                Analyze
              </TabsTrigger>
            </TabsList>

            <Card>
              <CardContent className="p-6">
                <TabsContent value="refactor" className="mt-0">
                  <div className="mb-4">
                    <h2 className="text-lg font-semibold text-foreground">
                      Start a Refactoring Session
                    </h2>
                    <p className="text-sm text-muted-foreground mt-1">
                      Describe what you want refactored and hit go.
                    </p>
                  </div>
                  <RefactorForm defaultInputType={selectedInput} />
                </TabsContent>

                <TabsContent value="analyze" className="mt-0">
                  <div className="mb-4">
                    <h2 className="text-lg font-semibold text-foreground">
                      Quick Analysis
                    </h2>
                    <p className="text-sm text-muted-foreground mt-1">
                      Get immediate insights into complexity and code quality.
                    </p>
                  </div>
                  <AnalysisView />
                </TabsContent>
              </CardContent>
            </Card>
          </Tabs>
        </div>
      </div>
    </Layout>
  );
}
