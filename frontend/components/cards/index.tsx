"use client";

import type { AnyCard } from "@/lib/types";

import { AllocationFormCard as AllocationFormCardCmp } from "./AllocationFormCard";
import { BalanceViewCard as BalanceViewCardCmp } from "./BalanceViewCard";
import { ConfirmationCard as ConfirmationCardCmp } from "./ConfirmationCard";
import { SuccessCard as SuccessCardCmp } from "./SuccessCard";
import { UnknownCard as UnknownCardCmp } from "./UnknownCard";

export type CardHandlers = {
  onClose: () => void;
  onSubmit: (submission: Record<string, unknown>) => void;
};

export function renderCard(card: AnyCard, handlers: CardHandlers) {
  switch (card.card_type) {
    case "balance_view":
      return <BalanceViewCardCmp card={card as any} {...handlers} />;
    case "allocation_form":
      return <AllocationFormCardCmp card={card as any} {...handlers} />;
    case "confirmation":
      return <ConfirmationCardCmp card={card as any} {...handlers} />;
    case "success":
      return <SuccessCardCmp card={card as any} {...handlers} />;
    default:
      return <UnknownCardCmp card={card} {...handlers} />;
  }
}
