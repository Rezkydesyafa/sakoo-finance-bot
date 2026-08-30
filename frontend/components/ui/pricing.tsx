"use client";

import { buttonVariants } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { Check, Star } from "lucide-react";
import Link from "next/link";
import { useState, useRef } from "react";
import confetti from "canvas-confetti";
import NumberFlow from "@number-flow/react";

interface PricingPlan {
  name: string;
  price: string;
  yearlyPrice: string;
  period: string;
  features: string[];
  description: string;
  buttonText: string;
  href: string;
  isPopular: boolean;
}

interface PricingProps {
  plans: PricingPlan[];
  title?: string;
  description?: string;
}

export function Pricing({
  plans,
  title = "Simple, Transparent Pricing",
  description = "Choose the plan that works for you\nAll plans include access to our platform, lead generation tools, and dedicated support.",
}: PricingProps) {
  const [isMonthly, setIsMonthly] = useState(true);
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const switchRef = useRef<HTMLButtonElement>(null);

  const handleToggle = (checked: boolean) => {
    setIsMonthly(!checked);
    if (checked && switchRef.current) {
      const rect = switchRef.current.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;

      confetti({
        particleCount: 50,
        spread: 60,
        origin: {
          x: x / window.innerWidth,
          y: y / window.innerHeight,
        },
        colors: [
          "#c7ff00",
          "#4e6700",
          "#151f00",
          "#6F6F6F",
        ],
        ticks: 200,
        gravity: 1.2,
        decay: 0.94,
        startVelocity: 30,
        shapes: ["circle"],
      });
    }
  };

  return (
    <div className="container mx-auto py-20 px-4">
      <div className="text-center space-y-4 mb-12">
        <h2 className="text-4xl font-semibold tracking-tight sm:text-5xl text-[#1a1c1b]">
          {title}
        </h2>
        <p className="text-[#6F6F6F] text-lg whitespace-pre-line max-w-2xl mx-auto">
          {description}
        </p>
      </div>

      <div className="flex justify-center items-center mb-10">
        <label className="relative inline-flex items-center cursor-pointer">
          <Label className="cursor-pointer">
            <Switch
              ref={switchRef}
              checked={!isMonthly}
              onCheckedChange={handleToggle}
              className="relative data-[state=checked]:bg-[#c7ff00] data-[state=unchecked]:bg-[#e2e3e1]"
            />
          </Label>
        </label>
        <span className="ml-3 text-sm font-semibold text-[#1a1c1b]">
          Annual billing <span className="text-[#4e6700] font-semibold">(Save 20%)</span>
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto">
        {plans.map((plan, index) => (
          <motion.div
            key={index}
            initial={{ y: 50, opacity: 1 }}
            whileInView={
              isDesktop
                ? {
                    y: plan.isPopular ? -12 : 0,
                    opacity: 1,
                    scale: plan.isPopular ? 1.03 : 0.98,
                  }
                : {}
            }
            viewport={{ once: true }}
            transition={{
              duration: 1.2,
              type: "spring",
              stiffness: 100,
              damping: 30,
              delay: 0.2,
              opacity: { duration: 0.5 },
            }}
            className={cn(
              `rounded-2xl border p-6 bg-white text-center flex flex-col relative transition-all duration-300 hover:shadow-xl hover:-translate-y-2`,
              plan.isPopular
                ? "border-[#c7ff00] ring-2 ring-[#c7ff00]/40 shadow-md bg-[#ffffff]"
                : "border-[#E8E8E8] shadow-sm",
              !plan.isPopular && "mt-0"
            )}
          >
            {plan.isPopular && (
              <div className="absolute -top-3 right-6 bg-[#c7ff00] text-[#151f00] py-1 px-3 rounded-full flex items-center shadow-sm">
                <Star className="h-3.5 w-3.5 fill-current text-[#151f00]" />
                <span className="ml-1 text-xs font-semibold uppercase tracking-wider">
                  Popular
                </span>
              </div>
            )}
            <div className="flex-1 flex flex-col">
              <p className="text-sm font-semibold uppercase tracking-wider text-[#6F6F6F]">
                {plan.name}
              </p>
              <div className="mt-6 flex items-center justify-center gap-x-1">
                <span className="text-5xl font-semibold tracking-tight text-[#1a1c1b]">
                  <NumberFlow
                    value={
                      isMonthly ? Number(plan.price) : Number(plan.yearlyPrice)
                    }
                    format={{
                      style: "currency",
                      currency: "USD",
                      minimumFractionDigits: 0,
                      maximumFractionDigits: 0,
                    }}
                    transformTiming={{
                      duration: 500,
                      easing: "ease-out",
                    }}
                    willChange
                    className="font-variant-numeric: tabular-nums"
                  />
                </span>
                {plan.period !== "Next 3 months" && (
                  <span className="text-sm font-semibold leading-6 tracking-wide text-[#6F6F6F]">
                    / {plan.period}
                  </span>
                )}
              </div>

              <p className="mt-1 text-xs leading-5 text-[#6F6F6F]">
                {isMonthly ? "billed monthly" : "billed annually"}
              </p>

              <ul className="mt-6 gap-3 flex flex-col">
                {plan.features.map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-2.5 text-sm text-[#1a1c1b]">
                    <Check className="h-4 w-4 text-[#4e6700] mt-0.5 flex-shrink-0" />
                    <span className="text-left leading-tight">{feature}</span>
                  </li>
                ))}
              </ul>

              <hr className="w-full my-6 border-[#E8E8E8]" />

              <Link
                href={plan.href}
                className={cn(
                  buttonVariants({
                    variant: "outline",
                  }),
                  "group relative w-full gap-2 overflow-hidden text-base font-semibold tracking-tight py-3 rounded-full transition-all duration-300",
                  plan.isPopular
                    ? "bg-[#c7ff00] text-[#151f00] hover:bg-[#b8ee00] border-transparent shadow-sm"
                    : "bg-[#f4f4f2] text-[#1a1c1b] hover:bg-[#e2e3e1] border-transparent"
                )}
              >
                {plan.buttonText}
              </Link>
              <p className="mt-4 text-xs leading-5 text-[#6F6F6F]">
                {plan.description}
              </p>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
