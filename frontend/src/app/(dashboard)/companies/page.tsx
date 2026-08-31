"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Building2, Plus, Search, ChevronDown, Play, Pause, Trash2, Eye } from "lucide-react";

interface Company {
  id: number; name: string; slug: string; status: string;
  industry: string; contact_email: string; created_at: string;
  database_name: string;
}

const statusColors: Record<string, string> = {
  active: "bg-green-500/20 text-green-400",
  trial: "bg-amber-500/20 text-amber-400",
  suspended: "bg-red-500/20 text-red-400",
  inactive: "bg-slate-500/20 text-slate-400",
};

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", industry: "", contact_email: "" });
  const [creating, setCreating] = useState(false);

  const load = () => {
    api.get("/admin/security/companies").then(({ data }) => {
      if (data.success) setCompanies(data.companies);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.post("/admin/security/companies/provision", form);
      setShowCreate(false);
      setForm({ name: "", slug: "", industry: "", contact_email: "" });
      load();
    } catch (err) { void err; }
    setCreating(false);
  };

  const transition = async (id: number, action: string) => {
    if (!confirm(`Are you sure you want to ${action} this company?`)) return;
    await api.post(`/admin/security/companies/${id}/transition`, { action });
    load();
  };

  const filtered = companies.filter((c) => c.name?.toLowerCase().includes(search.toLowerCase()) || c.slug?.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Companies</h1>
          <p className="text-slate-400 text-sm mt-1">{companies.length} total companies</p>
        </div>
        <button onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-medium transition">
          <Plus className="w-4 h-4" /> New Company
        </button>
      </div>

      {showCreate && (
        <form onSubmit={handleCreate} className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 space-y-4">
          <h3 className="text-white font-semibold">Create New Company</h3>
          <div className="grid grid-cols-2 gap-4">
            <input placeholder="Company Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" required />
            <input placeholder="Slug (e.g. abc-tourism)" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })}
              className="px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" required />
            <input placeholder="Industry" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })}
              className="px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
            <input placeholder="Contact Email" type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
              className="px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
          </div>
          <div className="flex gap-3">
            <button type="submit" disabled={creating}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white rounded-xl text-sm font-medium transition">
              {creating ? "Creating..." : "Create Company"}
            </button>
            <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-xl text-sm transition">
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="relative">
        <Search className="absolute right-3 top-3 w-4 h-4 text-slate-400" />
        <input placeholder="Search companies..." value={search} onChange={(e) => setSearch(e.target.value)}
          className="w-full pr-10 pl-4 py-2.5 bg-slate-800/50 border border-slate-700/50 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><div className="w-8 h-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" /></div>
      ) : (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-400 border-b border-slate-700/50">
                <th className="text-right py-3 px-4">Company</th>
                <th className="text-right py-3 px-4">Slug</th>
                <th className="text-right py-3 px-4">Industry</th>
                <th className="text-right py-3 px-4">Status</th>
                <th className="text-right py-3 px-4">Email</th>
                <th className="text-right py-3 px-4">Created</th>
                <th className="text-right py-3 px-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id} className="border-b border-slate-700/30 hover:bg-slate-700/20 transition">
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 bg-blue-600/20 rounded-lg flex items-center justify-center">
                        <Building2 className="w-4 h-4 text-blue-400" />
                      </div>
                      <span className="text-white font-medium">{c.name}</span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-slate-400 font-mono text-xs">{c.slug}</td>
                  <td className="py-3 px-4 text-slate-300">{c.industry || "—"}</td>
                  <td className="py-3 px-4">
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColors[c.status] || "bg-slate-500/20 text-slate-400"}`}>
                      {c.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-400 text-xs">{c.contact_email}</td>
                  <td className="py-3 px-4 text-slate-500 text-xs">{c.created_at?.slice(0, 10)}</td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-1">
                      {c.status === "active" && (
                        <button onClick={() => transition(c.id, "suspend")} title="Suspend"
                          className="p-1.5 hover:bg-amber-500/20 rounded-lg transition text-amber-400">
                          <Pause className="w-3.5 h-3.5" />
                        </button>
                      )}
                      {c.status === "suspended" && (
                        <button onClick={() => transition(c.id, "activate")} title="Activate"
                          className="p-1.5 hover:bg-green-500/20 rounded-lg transition text-green-400">
                          <Play className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && <p className="text-center text-slate-500 py-8">No companies found</p>}
        </div>
      )}
    </div>
  );
}
