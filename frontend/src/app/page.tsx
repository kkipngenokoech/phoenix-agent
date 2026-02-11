import RefactorForm from "@/components/RefactorForm";
import AnalysisView from "@/components/AnalysisView";

export default function Dashboard() {
  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Dashboard</h1>
        <p className="text-gray-500 text-sm">
          Observe &rarr; Reason &rarr; Plan &rarr; Decide &rarr; Act &rarr; Verify &rarr; Update
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* Refactoring */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            Start Refactoring
          </h2>
          <RefactorForm />
        </div>

        {/* Analysis */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            Code Analysis
          </h2>
          <AnalysisView />
        </div>
      </div>
    </div>
  );
}
