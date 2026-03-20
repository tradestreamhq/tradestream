import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { RegisterPage } from "../RegisterPage";
import * as AuthContext from "@/context/AuthContext";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderRegister(authOverrides = {}) {
  const defaultAuth = {
    user: null,
    isLoading: false,
    isAuthenticated: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  };

  vi.mocked(AuthContext.useAuth).mockReturnValue({
    ...defaultAuth,
    ...authOverrides,
  });

  return render(
    <MemoryRouter>
      <RegisterPage />
    </MemoryRouter>
  );
}

describe("RegisterPage", () => {
  it("renders registration form", () => {
    renderRegister();
    expect(
      screen.getByRole("heading", { name: "Create Account" })
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("submits registration form", async () => {
    const register = vi.fn().mockResolvedValue(undefined);
    renderRegister({ register });

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Test User" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "test@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Account" }));

    await waitFor(() => {
      expect(register).toHaveBeenCalledWith(
        "test@test.com",
        "password123",
        "Test User"
      );
    });
  });

  it("shows error on failed registration", async () => {
    const register = vi
      .fn()
      .mockRejectedValue(new Error("Email already exists"));
    renderRegister({ register });

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Test" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "test@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Account" }));

    await waitFor(() => {
      expect(screen.getByText("Email already exists")).toBeInTheDocument();
    });
  });

  it("has link to login page", () => {
    renderRegister();
    expect(screen.getByText("Sign in")).toBeInTheDocument();
  });
});
