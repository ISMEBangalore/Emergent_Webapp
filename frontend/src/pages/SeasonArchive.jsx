import { useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { ArrowLeft, Archive, Snowflake, ArrowsLeftRight, Warning, Trash, FunnelSimple, ChartLineUp } from "@phosphor-icons/react";
import { fmtInt } from "@/lib/format";
import { Chips, CompareFunnelTable, FunnelTable, mergeAllPrograms, seasonRangeLabel, seasonShortLabel } from "@/components/VerifiedLeadFunnelTable";
import { ReportTabs } from "@/components/ReportTabs";
import { KpiCards } from "@/components/KpiCards";

const StatusBadge = ({ frozen }) =>
  frozen ? (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200 text-[11px] font-semibold">
      <Snowflake size={11} weight="bold" /> Frozen
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[11px] font-semibold">
      Live
    </span>
  );

export default function SeasonArchive() {
  const nav = useNavigate();
  const [seasons, setSeasons] = useState([]);
  const [loadingList, setLoadingList] = useState(true);

  const [selectedId, setSelectedId] = useState("");
  const [selectedData, setSelectedData] = useState(null);
  const [loadingSelected, setLoadingSelected] = useState(false);
  const [prog, setProg] = useState("All");
  const [freezing, setFreezing] = useState(false);

  const [viewMode, setViewMode] = useState("funnel"); // "funnel" | "report"
  const [reportData, setReportData] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [reportLoadedFor, setReportLoadedFor] = useState("");

  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");
  const [compareProg, setCompareProg] = useState("All");
  const [compareDataA, setCompareDataA] = useState(null);
  const [compareDataB, setCompareDataB] = useState(null);
  const [compareLoading, setCompareLoading] = useState(false);

  const loadSeasons = useCallback(async () => {
    setLoadingList(true);
    try {
      const s = await api.listSeasons();
      setSeasons(s || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not load saved seasons.");
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => { loadSeasons(); }, [loadSeasons]);

  const selectSeason = async (id) => {
    setSelectedId(id);
    setLoadingSelected(true);
    setViewMode("funnel");
    setReportData(null);
    setReportLoadedFor("");
    try {
      const d = await api.getSeasonAnalysis(id);
      setSelectedData(d);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not load that season.");
    } finally {
      setLoadingSelected(false);
    }
  };

  const loadReport = async (id) => {
    if (reportLoadedFor === id) return;
    setLoadingReport(true);
    try {
      const d = await api.getSeasonReport(id);
      setReportData(d);
      setReportLoadedFor(id);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not load the full report for this season.");
    } finally {
      setLoadingReport(false);
    }
  };

  const showViewMode = (mode) => {
    setViewMode(mode);
    if (mode === "report" && selectedId) loadReport(selectedId);
  };

  const freezeSelected = async () => {
    if (!selectedId) return;
    setFreezing(true);
    try {
      const d = await api.freezeSeason(selectedId);
      setSelectedData(d);
      setReportData(null);
      setReportLoadedFor("");
      if (viewMode === "report") loadReport(selectedId);
      toast.success(`Froze "${d.season?.label}" — it's now a permanent, instant-loading snapshot.`);
      await loadSeasons();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not freeze this season.");
    } finally {
      setFreezing(false);
    }
  };

  const unfreezeSelected = async () => {
    if (!selectedId) return;
    try {
      await api.unfreezeSeason(selectedId);
      toast.success("Reverted to live — it'll recompute from current data again.");
      await loadSeasons();
      selectSeason(selectedId);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not unfreeze this season.");
    }
  };

  const deleteSelected = async () => {
    if (!selectedId) return;
    const s = seasons.find((x) => x.id === selectedId);
    try {
      await api.deleteSeason(selectedId);
      toast.success(`Deleted "${s?.label || "season"}".`);
      setSelectedId("");
      setSelectedData(null);
      await loadSeasons();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not delete this season.");
    }
  };

  const runCompare = async () => {
    if (!compareA || !compareB) { toast.error("Pick two seasons to compare."); return; }
    setCompareLoading(true);
    try {
      const [a, b] = await Promise.all([api.getSeasonAnalysis(compareA), api.getSeasonAnalysis(compareB)]);
      setCompareDataA(a);
      setCompareDataB(b);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not load one of the selected seasons.");
    } finally {
      setCompareLoading(false);
    }
  };

  const progOptions = ["All", ...(selectedData?.programs || [])];
  const rows = useMemo(() => {
    if (!selectedData) return [];
    return prog === "All" ? mergeAllPrograms(selectedData.funnel, selectedData.programs || []) : (selectedData.funnel?.[prog] || []);
  }, [selectedData, prog]);

  const compareProgOptions = ["All", ...(compareDataA?.programs || compareDataB?.programs || [])];
  const compareRowsA = useMemo(() => {
    if (!compareDataA) return null;
    return compareProg === "All"
      ? mergeAllPrograms(compareDataA.funnel, compareDataA.programs)
      : (compareDataA.funnel?.[compareProg] || []);
  }, [compareDataA, compareProg]);
  const compareRowsB = useMemo(() => {
    if (!compareDataB) return null;
    return compareProg === "All"
      ? mergeAllPrograms(compareDataB.funnel, compareDataB.programs)
      : (compareDataB.funnel?.[compareProg] || []);
  }, [compareDataB, compareProg]);

  const selectedSeason = selectedData?.season;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <button onClick={() => nav(-1)} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-[#002FA7] mb-4" data-testid="back-btn">
        <ArrowLeft size={16} weight="bold" /> Back
      </button>

      <div className="flex items-center gap-2 mb-1">
        <Archive size={26} weight="bold" color="#002FA7" />
        <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-900" data-testid="archive-title">
          Season Archive
        </h1>
      </div>
      <p className="text-slate-500 mt-1 mb-5">
        Every season saved from Verified Lead Analysis, in one permanent place. A <strong>Live</strong> season keeps
        recomputing from current data (right for an ongoing cycle); a <strong>Frozen</strong> one is computed once and
        stored — instant to view, immune to future date-boundary or upload changes, and safe to keep around even after
        its underlying weekly reports are eventually cleaned up.
      </p>

      {loadingList ? (
        <div className="h-40 bg-slate-100 rounded-md animate-pulse" />
      ) : seasons.length === 0 ? (
        <div className="bg-white border border-dashed border-slate-300 rounded-md p-12 text-center text-slate-500" data-testid="archive-empty">
          No seasons saved yet — go to Verified Lead Analysis and use "Save as Season" first.
        </div>
      ) : (
        <>
          <div className="bg-white border border-slate-200 rounded-md p-5 mb-6">
            <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
              <div className="flex items-end gap-3">
                <div>
                  <label className="text-xs uppercase tracking-wide text-slate-500 block mb-1.5">Season</label>
                  <Select value={selectedId} onValueChange={selectSeason}>
                    <SelectTrigger className="w-64" data-testid="archive-season-select">
                      <SelectValue placeholder="Choose a saved season" />
                    </SelectTrigger>
                    <SelectContent>
                      {seasons.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.label} <span className="text-slate-400">({seasonRangeLabel(s)}) {s.frozen ? "❄" : ""}</span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {selectedSeason && <StatusBadge frozen={selectedSeason.frozen} />}
              </div>
              {selectedSeason && (
                <div className="flex items-center gap-2">
                  {selectedSeason.frozen ? (
                    <Button variant="outline" size="sm" data-testid="archive-unfreeze-btn" onClick={unfreezeSelected} className="gap-1.5">
                      Unfreeze (make live again)
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" data-testid="archive-freeze-btn" onClick={freezeSelected} disabled={freezing} className="gap-1.5">
                      <Snowflake size={15} weight="bold" /> {freezing ? "Freezing…" : "Freeze this season"}
                    </Button>
                  )}
                  <Button
                    variant="outline" size="sm" data-testid="archive-delete-btn" onClick={deleteSelected}
                    className="gap-1.5 text-red-600 hover:text-red-700"
                  >
                    <Trash size={15} weight="bold" />
                  </Button>
                </div>
              )}
            </div>

            {selectedSeason && !selectedSeason.frozen && (
              <div className="flex items-start gap-2 px-3 py-2 rounded-md bg-slate-50 border border-slate-200 text-slate-600 text-xs" data-testid="archive-live-hint">
                <Snowflake size={14} weight="bold" className="mt-0.5 shrink-0" />
                <span>
                  This season is still live — every view recomputes it from current reports. Freeze it once the period
                  is truly closed (e.g. the admissions cycle has ended) to make future views instant and stop it
                  depending on the underlying reports staying around.
                </span>
              </div>
            )}
            {selectedSeason?.frozen && (
              <div className="flex items-start gap-2 px-3 py-2 rounded-md bg-sky-50 border border-sky-200 text-sky-800 text-xs" data-testid="archive-frozen-hint">
                <Snowflake size={14} weight="bold" className="mt-0.5 shrink-0" />
                <span>Frozen {selectedSeason.frozen_at ? `on ${selectedSeason.frozen_at.slice(0, 10)}` : ""} — this is a stored, unchanging snapshot.</span>
              </div>
            )}
          </div>

          {selectedId && (
            loadingSelected ? (
              <div className="h-72 bg-slate-100 rounded-md animate-pulse mb-6" />
            ) : selectedData ? (
              <div className="mb-8">
                <div className="inline-flex rounded-md border border-slate-200 bg-white p-1 mb-4" data-testid="archive-viewmode-toggle">
                  <button
                    onClick={() => showViewMode("funnel")}
                    data-testid="archive-viewmode-funnel"
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                      viewMode === "funnel" ? "bg-[#002FA7] text-white" : "text-slate-600 hover:text-[#002FA7]"
                    }`}
                  >
                    <FunnelSimple size={15} weight="bold" /> VLA Funnel
                  </button>
                  <button
                    onClick={() => showViewMode("report")}
                    data-testid="archive-viewmode-report"
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                      viewMode === "report" ? "bg-[#002FA7] text-white" : "text-slate-600 hover:text-[#002FA7]"
                    }`}
                  >
                    <ChartLineUp size={15} weight="bold" /> Full Report
                  </button>
                </div>

                {viewMode === "funnel" ? (
                  <>
                    <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                      <Chips options={progOptions} value={prog} onChange={setProg} testidPrefix="archive-prog" />
                      <p className="text-xs text-slate-400">
                        {fmtInt(selectedData.reports_included)} report{selectedData.reports_included === 1 ? "" : "s"} · {fmtInt(selectedData.applications_included)} application{selectedData.applications_included === 1 ? "" : "s"} in range
                      </p>
                    </div>
                    <div className="bg-white border border-slate-200 rounded-md p-5">
                      <FunnelTable rows={rows} testid="archive-funnel-table" />
                    </div>
                  </>
                ) : loadingReport ? (
                  <div className="h-72 bg-slate-100 rounded-md animate-pulse" data-testid="archive-report-loading" />
                ) : reportData ? (
                  <div data-testid="archive-report-view">
                    <KpiCards kpis={reportData.kpis} />
                    <ReportTabs result={reportData.result} />
                  </div>
                ) : null}
              </div>
            ) : null
          )}

          <div className="bg-white border border-slate-200 rounded-md p-5 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <ArrowsLeftRight size={18} weight="bold" color="#002FA7" />
              <h3 className="font-display font-bold text-slate-900">Compare two seasons</h3>
            </div>
            {seasons.length < 2 ? (
              <p className="text-sm text-slate-500" data-testid="archive-compare-empty">
                Save at least two seasons to compare them side by side.
              </p>
            ) : (
              <>
                <div className="flex flex-wrap items-end gap-3">
                  <div>
                    <label className="text-xs uppercase tracking-wide text-slate-500 block mb-1.5">Season A</label>
                    <Select value={compareA} onValueChange={setCompareA}>
                      <SelectTrigger className="w-64" data-testid="archive-compare-a-select"><SelectValue placeholder="Choose season" /></SelectTrigger>
                      <SelectContent>{seasons.map((s) => <SelectItem key={s.id} value={s.id}>{s.label} <span className="text-slate-400">({seasonRangeLabel(s)})</span></SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-xs uppercase tracking-wide text-slate-500 block mb-1.5">Season B</label>
                    <Select value={compareB} onValueChange={setCompareB}>
                      <SelectTrigger className="w-64" data-testid="archive-compare-b-select"><SelectValue placeholder="Choose season" /></SelectTrigger>
                      <SelectContent>{seasons.map((s) => <SelectItem key={s.id} value={s.id}>{s.label} <span className="text-slate-400">({seasonRangeLabel(s)})</span></SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <Button data-testid="archive-compare-run" onClick={runCompare} disabled={compareLoading} className="bg-[#002FA7] hover:bg-[#002FA7]/90">
                    {compareLoading ? "Loading…" : "Compare"}
                  </Button>
                </div>
                {(compareDataA || compareDataB) && (
                  <div className="mt-4">
                    <Chips options={compareProgOptions} value={compareProg} onChange={setCompareProg} testidPrefix="archive-compare-prog" />
                  </div>
                )}
              </>
            )}
          </div>

          {compareDataA && compareDataB && (
            <>
              {compareDataA.season?.id === compareDataB.season?.id && (
                <div className="flex items-start gap-2 mb-4 px-4 py-3 rounded-md bg-red-50 border border-red-200 text-red-800 text-sm" data-testid="archive-compare-same-season-warning">
                  <Warning size={16} weight="fill" className="mt-0.5 shrink-0" />
                  <span>Season A and Season B are the same saved season — pick two different ones to compare.</span>
                </div>
              )}
              <div className="bg-white border border-slate-200 rounded-md p-5">
                <div className="grid sm:grid-cols-2 gap-4 mb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-400">A ({seasonShortLabel(compareDataA.season)})</span>
                      <h4 className="text-sm font-bold text-slate-800">{compareDataA.season?.label}</h4>
                      <StatusBadge frozen={compareDataA.season?.frozen} />
                    </div>
                    <p className="text-xs text-slate-400">{seasonRangeLabel(compareDataA.season)}</p>
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-400">B ({seasonShortLabel(compareDataB.season)})</span>
                      <h4 className="text-sm font-bold text-slate-800">{compareDataB.season?.label}</h4>
                      <StatusBadge frozen={compareDataB.season?.frozen} />
                    </div>
                    <p className="text-xs text-slate-400">{seasonRangeLabel(compareDataB.season)}</p>
                  </div>
                </div>
                <CompareFunnelTable
                  rowsA={compareRowsA || []} rowsB={compareRowsB || []}
                  labelA={seasonShortLabel(compareDataA.season)} labelB={seasonShortLabel(compareDataB.season)}
                  testid="archive-compare-table"
                />
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
