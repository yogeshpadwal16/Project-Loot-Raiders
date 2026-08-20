import React, { useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  createColumnHelper
} from '@tanstack/react-table';
import { Search, ExternalLink, RefreshCw, Trash2, CheckCircle } from 'lucide-react';
import { DealItem } from '../../types/api';

interface LootDataTableProps {
  data: DealItem[];
  onRefresh: () => void;
}

const columnHelper = createColumnHelper<DealItem>();

export const LootDataTable: React.FC<LootDataTableProps> = ({ data, onRefresh }) => {
  const [globalFilter, setGlobalFilter] = useState('');

  const columns = [
    columnHelper.accessor('id', {
      header: 'ID / ASIN',
      cell: (info) => <span className="font-mono text-xs text-slate-400">{info.getValue()}</span>
    }),
    columnHelper.accessor('title', {
      header: 'Product Title',
      cell: (info) => (
        <span className="font-semibold text-slate-100 line-clamp-1 max-w-xs sm:max-w-sm" title={info.getValue()}>
          {info.getValue()}
        </span>
      )
    }),
    columnHelper.accessor('platform', {
      header: 'Platform',
      cell: (info) => (
        <span className="text-[11px] font-black uppercase px-2 py-0.5 rounded-md bg-slate-800 text-orange-400 border border-slate-700">
          {info.getValue()}
        </span>
      )
    }),
    columnHelper.accessor('price', {
      header: 'Price',
      cell: (info) => <span className="font-bold text-emerald-400">₹{info.getValue().toLocaleString('en-IN')}</span>
    }),
    columnHelper.accessor('mrp', {
      header: 'MRP',
      cell: (info) => <span className="text-slate-500 line-through">₹{info.getValue().toLocaleString('en-IN')}</span>
    }),
    columnHelper.accessor('discount', {
      header: 'Discount',
      cell: (info) => <span className="font-black text-orange-400">{info.getValue().toFixed(0)}% OFF</span>
    }),
    columnHelper.accessor('deal_score', {
      header: 'Score',
      cell: (info) => (
        <span className="font-bold text-amber-300 bg-amber-500/10 px-2 py-0.5 rounded-md border border-amber-500/20">
          {info.getValue().toFixed(0)}
        </span>
      )
    }),
    columnHelper.accessor('url', {
      header: 'Action',
      cell: (info) => (
        <a
          href={info.row.original.affiliate_url || info.getValue()}
          target="_blank"
          rel="noopener noreferrer"
          className="p-1.5 bg-slate-800 hover:bg-orange-500 hover:text-slate-950 text-slate-300 rounded-lg inline-flex transition-all"
        >
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      )
    })
  ];

  const table = useReactTable({
    data,
    columns,
    state: { globalFilter },
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 10 } }
  });

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-2xl space-y-4">
      
      {/* Table Header Controls */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            value={globalFilter ?? ''}
            onChange={(e) => setGlobalFilter(e.target.value)}
            placeholder="Search deal titles, IDs, platforms..."
            className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-orange-500"
          />
        </div>

        <button
          onClick={onRefresh}
          className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2 rounded-xl text-xs font-bold transition-all border border-slate-700/50"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Table
        </button>
      </div>

      {/* TanStack Table Render */}
      <div className="overflow-x-auto rounded-2xl border border-slate-800">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950 text-slate-400 font-bold uppercase tracking-wider border-b border-slate-800">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="p-3">
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>

          <tbody className="divide-y divide-slate-800/60 bg-slate-900/50">
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="hover:bg-slate-800/40 transition-colors">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="p-3">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      <div className="flex items-center justify-between text-xs text-slate-400 pt-2">
        <span>
          Page <strong>{table.getState().pagination.pageIndex + 1}</strong> of <strong>{table.getPageCount()}</strong>
        </span>

        <div className="flex gap-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg disabled:opacity-40 font-semibold text-slate-300 hover:text-white"
          >
            Previous
          </button>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg disabled:opacity-40 font-semibold text-slate-300 hover:text-white"
          >
            Next
          </button>
        </div>
      </div>

    </div>
  );
};
