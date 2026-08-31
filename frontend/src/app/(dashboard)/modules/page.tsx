"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Package, Plus, Check, X } from "lucide-react";

interface Module { id: number; code: string; name: string; description: string; category: string; is_active: boolean }

export default function ModulesPage() {
  const [modules, setModules] = useState<Module[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => { api.get("/admin/security/modules").then(({ data }) => { if (data.success) setModules(data.modules); }).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  const categories = [...new Set(modules.map((m) => m.category))];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Module Catalog</h1>
        <p className="text-slate-400 text-sm mt-1">{modules.length} modules in catalog</p>
      </div>

      {loading ? <div className="flex justify-center py-20"><div className="w-8 h-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" /></div> : (
        <div className="space-y-6">
          {categories.map((cat) => (
            <div key={cat}>
              <h2 className="text-lg font-semibold text-white mb-3 capitalize">{cat}</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {modules.filter((m) => m.category === cat).map((m) => (
                  <div key={m.id} className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5 hover:border-blue-500/30 transition">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Package className="w-4 h-4 text-cyan-400" />
                        <h3 className="text-white font-medium">{m.name}</h3>
                      </div>
                      <span className={`w-2 h-2 rounded-full ${m.is_active ? "bg-green-400" : "bg-slate-500"}`} />
                    </div>
                    <p className="text-slate-400 text-xs">{m.description || m.code}</p>
                    <p className="text-slate-500 text-[10px] mt-2 uppercase tracking-wider">{m.code}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
