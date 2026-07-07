export type Transaction = {
  id: number;
  type: "income" | "expense";
  amount: number;
  category_id: number | null;
  category_name: string;
  description: string;
  transaction_date: string;
  created_at?: string;
  source: string;
};

export type ChatMessage = {
  id: number;
  sender: "user" | "bot";
  text: string;
  time: string;
};
