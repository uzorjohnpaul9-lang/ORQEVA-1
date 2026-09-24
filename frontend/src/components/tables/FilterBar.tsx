interface FilterBarProps {
  filters: { key: string; label: string; options: { value: string; label: string }[] }[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
}

export function FilterBar({ filters, values, onChange }: FilterBarProps) {
  return (
    <div className="flex flex-wrap gap-3">
      {filters.map((f) => (
        <select
          key={f.key}
          value={values[f.key] || ""}
          onChange={(e) => onChange(f.key, e.target.value)}
          className="bg-bg-tertiary border border-border rounded-lg px-3 py-2 text-sm text-text-primary outline-none focus:border-green/50 transition-colors"
        >
          <option value="">{f.label}</option>
          {f.options.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      ))}
    </div>
  );
}
