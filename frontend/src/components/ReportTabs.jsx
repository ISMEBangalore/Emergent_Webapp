import { useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ReportTable } from "@/components/ReportTable";

const Chips = ({ options, value, onChange, testidPrefix, labelFor }) => (
  <div className="flex flex-wrap items-center gap-2 mb-3" data-testid={`${testidPrefix}-filter`}>
    <span className="text-xs uppercase tracking-wide text-slate-500 mr-1">{labelFor}:</span>
    {options.map((opt) => (
      <button
        key={opt}
        data-testid={`${testidPrefix}-${opt}`}
        onClick={() => onChange(opt)}
        className={`px-3 py-1 rounded-full text-sm border transition-colors ${
          value === opt
            ? "bg-[#002FA7] text-white border-[#002FA7]"
            : "border-slate-200 text-slate-600 hover:border-[#002FA7] hover:text-[#002FA7]"
        }`}
      >
        {opt === "All" ? "All" : opt}
      </button>
    ))}
  </div>
);

export const ReportTabs = ({ result, publisherPanel = null }) => {
  const byProgram = result.publisher_reports || null;    // publisher columns, per program
  const byPublisher = result.program_reports || null;    // program columns, per publisher
  const fallbackPub = result.publisher_report;

  const [pubProg, setPubProg] = useState("All");         // program selected in "By Publisher"
  const [progPub, setProgPub] = useState("All");         // publisher selected in "By Program per Publisher"

  const pub = byProgram ? (byProgram[pubProg] || byProgram.All) : fallbackPub;
  const pubEmpty =
    !pub || !pub.programs?.length || (pub.programs.length === 1 && pub.programs[0] === "Unknown");

  const progOptions = byProgram ? ["All", ...(result.programs || [])] : ["All"];
  const publisherOptions = byPublisher
    ? ["All", ...Object.keys(byPublisher).filter((k) => k !== "All")]
    : [];
  const progReport = byPublisher ? (byPublisher[progPub] || byPublisher.All) : result;

  return (
    <Tabs defaultValue="program" className="mt-8" data-testid="report-tabs">
      <TabsList className="bg-slate-100 flex-wrap h-auto">
        <TabsTrigger value="program" data-testid="tab-program">By Program</TabsTrigger>
        <TabsTrigger value="publisher" data-testid="tab-publisher">By Publisher</TabsTrigger>
        {byPublisher && !pubEmpty && (
          <TabsTrigger value="pub-program" data-testid="tab-pub-program">Programs per Publisher</TabsTrigger>
        )}
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
              <Chips options={progOptions} value={pubProg} onChange={setPubProg}
                     testidPrefix="pub-prog" labelFor="Program" />
            )}
            <ReportTable result={pub} />
          </>
        )}
      </TabsContent>

      {byPublisher && !pubEmpty && (
        <TabsContent value="pub-program" className="mt-4">
          <Chips options={publisherOptions} value={progPub} onChange={setProgPub}
                 testidPrefix="prog-pub" labelFor="Publisher" />
          <ReportTable result={progReport} />
        </TabsContent>
      )}
    </Tabs>
  );
};
