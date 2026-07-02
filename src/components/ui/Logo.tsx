import React from 'react';
import { Cpu } from 'lucide-react';

export function Logo() {
  return (
    <div className="flex items-center gap-2 text-industrial-blue font-bold tracking-wider select-none">
      <Cpu className="w-6 h-6 stroke-[2]" />
      <span className="text-white text-base">IOB</span>
      <span className="text-xs text-industrial-slate font-mono px-1.5 py-0.5 bg-gray-800 rounded border border-gray-700">
        v1.0
      </span>
    </div>
  );
}

export default Logo;
