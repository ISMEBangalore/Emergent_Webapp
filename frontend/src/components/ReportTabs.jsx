import { useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ReportTable } from "@/components/ReportTable";

export const ReportTabs = ({ result, publisherPanel = null }) => {
  const byProgram = result.publisher_reports || null;
  const fallback = result.publisher_report;
  const options = byProgram ? ["All", ...(result.programs || [])] : ["All"];
  const [pubProg, setPubProg] = useState("All");

  const pub = byProgram ? (byProgram[pubProg] || byProgram.All) : fallback;
  const pubEmpty =
    !pub || !pub.programs?.length || (pub.programs.length === 1 && pub.programs[0] === "Unknown");

  return (
    <Tabs defaultValue="program" className="mt-8" data-testid="report-tabs">
      <TabsList className="bg-slate-100">
        <TabsTrigger value="program" data-testid="tab-program">By Program</TabsTrigger>
        <TabsTrigger value="publisher" data-testid="tab-publisher">By Publisher</TabsTrigger>
      </TabsList>
      <TabsContent value="program" className="mt-4">
        <ReportTable result={result} />
      </TabsContent>
      <TabsContent value="publisher" className="mt-4">
        {pubEmpty ? (
          <div className="border border-dashed border-slate-300 rounded-md p-10 text-center text-slate-500"
               data-testid="publisher-empty">
            No publisher data found in this file (the <b>Publisher Name</b> column was empty).
            Your real CRM export will populate this automatically.
          </div>
        ) : (
          <>
            {publisherPanel}
            {byProgram && (
              <div className="flex flex-wrap items-center gap-2 mb-3" data-testid="publisher-program-filter">
                <span className="text-xs uppercase tracking-wide text-slate-500 mr-1">Program:</span>
                {options.map((opt) => (
                  <button
                    key={opt}
                    data-testid={`pub-prog-${opt}`}
                    onClick={() => setPubProg(opt)}
                    className={`px-3 py-1 rounded-full text-sm border transition-colors ${
                      pubProg === opt
                        ? "bg-[#002FA7] text-white border-[#002FA7]"
                        : "border-slate-200 text-slate-600 hover:border-[#002FA7] hover:text-[#002FA7]"
                    }`}
                  >
                    {opt === "All" ? "All programs" : opt}
                  </button>
                ))}
              </div>
            )}
            <ReportTable result={pub} />
          </>
        )}
      </TabsContent>
    </Tabs>
  );
};
