"use client";

import { Pricing } from "@/components/ui/pricing";

const demoPlans = [
  {
    name: "STARTER",
    price: "0",
    yearlyPrice: "0",
    period: "forever",
    features: [
      "1 Connected WhatsApp Account",
      "Manual AI Financial Category Tagging",
      "Basic Weekly Financial Summary PDF",
      "7 Days History logs",
      "Standard LLM model",
    ],
    description: "Cocok untuk personal use & pencatatan sederhana",
    buttonText: "Coba Gratis Sekarang",
    href: "/register",
    isPopular: false,
  },
  {
    name: "PROFESSIONAL",
    price: "15",
    yearlyPrice: "12",
    period: "per month",
    features: [
      "Up to 3 Connected WA Accounts",
      "Smart Auto-categorization (LLM)",
      "Daily, Weekly & Monthly PDF Export",
      "Interactive Dashboard & Budgeting",
      "Priority LLM (Fast Response)",
      "WhatsApp Reminder Alerts",
    ],
    description: "Sangat direkomendasikan untuk tracking optimal",
    buttonText: "Mulai Langganan",
    href: "/register",
    isPopular: true,
  },
  {
    name: "ENTERPRISE",
    price: "49",
    yearlyPrice: "39",
    period: "per month",
    features: [
      "Unlimited Connected WA Accounts",
      "Multi-user / Keluarga Shared Wallet",
      "Custom PDF Layout & Financial Advisor AI",
      "Unlimited History Logs & Backups",
      "Dedicated Whatsapp Gateway instance",
      "Direct Priority Support & SLA",
    ],
    description: "Pilihan tepat untuk keluarga besar & UKM",
    buttonText: "Hubungi Penjualan",
    href: "https://wa.me/something",
    isPopular: false,
  },
];

export function PricingBasic() {
  return (
    <div className="rounded-lg">
      <Pricing 
        plans={demoPlans}
        title="Pilih Paket Sakoo yang Sesuai"
        description="Pantau, rencanakan, dan atur keuangan personal Anda dengan integrasi AI & WhatsApp secara praktis."
      />
    </div>
  );
}
