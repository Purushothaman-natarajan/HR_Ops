import { useState } from "react";

interface Props {
  onSubmit: (query: string) => void;
  disabled?: boolean;
}

export function QueryInput({ onSubmit, disabled }: Props) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSubmit(query.trim());
      setQuery("");
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8, padding: 16 }}>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Ask an HR question..."
        disabled={disabled}
        style={{ flex: 1, padding: "8px 12px", borderRadius: 6, border: "1px solid #ccc" }}
      />
      <button
        type="submit"
        disabled={disabled || !query.trim()}
        style={{ padding: "8px 20px", borderRadius: 6, border: "none", background: "#4f46e5", color: "#fff", cursor: "pointer" }}
      >
        Submit
      </button>
    </form>
  );
}
