"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Modal } from "@/components/ui/Modal";

interface OrderFormProps {
  open: boolean;
  onClose: () => void;
}

export function OrderForm({ open, onClose }: OrderFormProps) {
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState("buy");
  const [quantity, setQuantity] = useState("");
  const [orderType, setOrderType] = useState("market");

  return (
    <Modal open={open} onClose={onClose} title="Place Order">
      <div className="space-y-4">
        <Input label="Symbol" placeholder="AAPL, EUR/USD, BTC/USDT" value={symbol} onChange={(e) => setSymbol(e.target.value)} />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Side" options={[{ value: "buy", label: "Buy" }, { value: "sell", label: "Sell" }]} value={side} onChange={(e) => setSide(e.target.value)} />
          <Select label="Order Type" options={[{ value: "market", label: "Market" }, { value: "limit", label: "Limit" }, { value: "stop", label: "Stop" }]} value={orderType} onChange={(e) => setOrderType(e.target.value)} />
        </div>
        <Input label="Quantity" placeholder="0.00" type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        <div className="flex gap-3 pt-2">
          <Button variant="secondary" className="flex-1" onClick={onClose}>Cancel</Button>
          <Button className="flex-1" onClick={onClose}>Place Order</Button>
        </div>
      </div>
    </Modal>
  );
}
