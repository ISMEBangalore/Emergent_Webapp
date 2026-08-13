import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";

export default function Latest() {
  const nav = useNavigate();
  useEffect(() => {
    api.listReports().then((list) => {
      const ready = list.find((r) => r.status === "ready" && r.source === "upload")
        || list.find((r) => r.status === "ready") || list[0];
      nav(ready ? `/report/${ready.id}` : "/generate", { replace: true });
    }).catch(() => nav("/generate", { replace: true }));
  }, [nav]);
  return (
    <div className="p-10 text-slate-500">Opening your latest comprehensive report…</div>
  );
}
