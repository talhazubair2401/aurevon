export const RETURN_STATUS: Record<string, string> = {
  requested: "Requested",
  approved: "Approved: on its way back",
  rejected: "Rejected",
  received: "Received: inspect it",
  inspected: "Inspected: complete it",
  completed: "Completed",
  cancelled: "Cancelled by the customer",
};

export const TICKET_STATUS: Record<string, string> = {
  open: "Waiting for us",
  waiting: "Waiting for the customer",
  closed: "Closed",
};

export const TICKET_CATEGORY: Record<string, string> = {
  order: "An order",
  delivery: "Delivery",
  return: "Returns and exchanges",
  payment: "Payment or refund",
  product: "A product or sizing",
  other: "Something else",
};

export const OUTCOME: Record<string, string> = {
  sellable: "Back to sellable stock",
  quarantine: "Quarantine (needs work or a second check)",
  damaged: "Damaged",
};
