import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  Alert,
  Button,
  ButtonLink,
  CheckboxField,
  Icon,
  Price,
  SelectField,
  SkipLink,
  TextField,
  Wordmark,
} from "./index";

afterEach(cleanup);

describe("Button", () => {
  it("is a real button, type=button by default, so it never submits a form by accident", () => {
    render(<Button>Add to bag</Button>);
    expect(screen.getByRole("button", { name: "Add to bag" })).toHaveProperty("type", "button");
  });

  it("stays focusable while busy, announces it, and ignores clicks", async () => {
    const onClick = vi.fn();
    render(
      <Button busy onClick={onClick}>
        Place order
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Place order" });
    expect(button.getAttribute("aria-busy")).toBe("true");
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(button.hasAttribute("disabled")).toBe(false);
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("calls onClick when not busy", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("ButtonLink stays a link", () => {
    render(<ButtonLink href="/en/shop">Shop All</ButtonLink>);
    expect(screen.getByRole("link", { name: "Shop All" }).getAttribute("href")).toBe("/en/shop");
  });
});

describe("form fields", () => {
  it("label, hint and error are wired to the input", () => {
    render(
      <TextField label="Email" hint="We send your receipt here." error="Enter a valid email." />,
    );
    const input = screen.getByLabelText("Email");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    const ids = input.getAttribute("aria-describedby")!.split(" ");
    expect(ids.map((id) => document.getElementById(id)?.textContent)).toEqual([
      "We send your receipt here.",
      "Enter a valid email.",
    ]);
  });

  it("valid fields are not marked invalid and have no dangling descriptions", () => {
    render(<TextField label="First name" />);
    const input = screen.getByLabelText("First name");
    expect(input.hasAttribute("aria-invalid")).toBe(false);
    expect(input.hasAttribute("aria-describedby")).toBe(false);
  });

  it("each field gets a unique id", () => {
    render(
      <>
        <TextField label="One" />
        <TextField label="Two" />
      </>,
    );
    expect(screen.getByLabelText("One").id).not.toBe(screen.getByLabelText("Two").id);
  });

  it("select and checkbox are labelled", async () => {
    render(
      <>
        <SelectField label="Size" error="Choose a size.">
          <option value="">Choose</option>
          <option value="m">M</option>
        </SelectField>
        <CheckboxField label="Remember me" />
      </>,
    );
    expect(screen.getByLabelText("Size").getAttribute("aria-invalid")).toBe("true");
    const box = screen.getByLabelText("Remember me");
    await userEvent.click(box);
    expect((box as HTMLInputElement).checked).toBe(true);
  });
});

describe("primitives", () => {
  it("errors are announced as alerts, other messages as status", () => {
    render(
      <>
        <Alert tone="error" title="Payment failed" />
        <Alert tone="success" title="Saved" />
      </>,
    );
    expect(screen.getByRole("alert").textContent).toBe("Payment failed");
    expect(screen.getByRole("status").textContent).toBe("Saved");
  });

  it("the wordmark is the interim AUREVON text, Latin and LTR even on Urdu pages", () => {
    render(
      <div lang="ur" dir="rtl">
        <Wordmark as="p" />
      </div>,
    );
    const mark = screen.getByText("AUREVON");
    expect(mark.getAttribute("lang")).toBe("en");
    expect(mark.getAttribute("dir")).toBe("ltr");
  });

  it("skip link points at the main landmark", () => {
    render(<SkipLink>Skip to main content</SkipLink>);
    expect(screen.getByRole("link", { name: "Skip to main content" }).getAttribute("href")).toBe(
      "#main",
    );
  });

  it("icons are hidden from assistive technology unless labelled", () => {
    const { container } = render(<Icon name="bag" />);
    expect(container.querySelector("svg")!.getAttribute("aria-hidden")).toBe("true");
    render(<Icon name="search" label="Search" />);
    expect(screen.getByRole("img", { name: "Search" })).toBeTruthy();
  });

  it("prices format the API's decimal string and stay left-to-right", () => {
    render(<Price amount="48500.00" locale="en" />);
    const price = screen.getByText(/48,500/);
    expect(price.getAttribute("dir")).toBe("ltr");
  });
});
