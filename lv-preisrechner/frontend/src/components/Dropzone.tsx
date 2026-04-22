"use client";

import { useCallback, useRef, useState } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/cn";

type Props = {
  onFile: (file: File) => void;
  accept?: string;
  hint?: string;
  busy?: boolean;
};

export function Dropzone({ onFile, accept = "application/pdf", hint, busy }: Props) {
  const [isOver, setIsOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const f = files[0];
      if (accept && !f.type.match(accept.replace("*", ".*")) && !f.name.toLowerCase().endsWith(".pdf")) {
        alert("Bitte eine PDF-Datei auswählen.");
        return;
      }
      onFile(f);
    },
    [accept, onFile],
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsOver(true);
      }}
      onDragLeave={() => setIsOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsOver(false);
        handleFiles(e.dataTransfer.files);
      }}
      onClick={() => !busy && inputRef.current?.click()}
      className={cn(
        "flex flex-col items-center justify-center h-48 rounded-xl border-2 border-dashed border-slate-300 bg-white text-center cursor-pointer transition-colors",
        isOver && "dropzone-active",
        busy && "opacity-60 cursor-wait",
      )}
    >
      <input
        type="file"
        ref={inputRef}
        accept={accept}
        onChange={(e) => handleFiles(e.target.files)}
        className="hidden"
        data-testid="dropzone-input"
      />
      <Upload className="w-10 h-10 text-bauplan-500 mb-3" />
      <div className="text-slate-900 font-medium">
        {busy ? "Wird hochgeladen…" : "PDF hier ablegen oder klicken"}
      </div>
      {hint && <div className="text-sm text-slate-500 mt-1 px-6">{hint}</div>}
    </div>
  );
}
