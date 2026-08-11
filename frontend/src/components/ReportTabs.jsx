import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ReportTable } from "@/components/ReportTable";

export const ReportTabs = ({ result }) => {
  const pub = result.publisher_report;
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
          <ReportTable result={pub} />
        )}
      </TabsContent>
    </Tabs>
  );
};
