export type Transaction = {
  id: number;
  type: "income" | "expense";
  amount: number;
  category_name: string;
  description: string;
  transaction_date: string;
  source: string;
};

export type ChatMessage = {
  id: number;
  sender: "user" | "bot";
  text: string;
  time: string;
};
