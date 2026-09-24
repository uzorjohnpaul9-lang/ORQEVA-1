import { clsx } from "clsx";

interface Column<T> {
  key: string;
  header: string;
  render: (item: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (item: T) => void;
}

export function DataTable<T extends { id: string }>({ columns, data, onRowClick }: DataTableProps<T>) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th key={col.key} className={clsx("text-left text-xs font-medium text-text-muted uppercase tracking-wider py-3 px-4", col.className)}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((item) => (
            <tr
              key={item.id}
              onClick={() => onRowClick?.(item)}
              className={clsx("border-b border-border/50 transition-colors", onRowClick && "cursor-pointer hover:bg-bg-hover")}
            >
              {columns.map((col) => (
                <td key={col.key} className={clsx("py-3 px-4", col.className)}>
                  {col.render(item)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length === 0 && (
        <div className="text-center py-12 text-text-muted">
          <p className="text-sm">No data available</p>
        </div>
      )}
    </div>
  );
}
