export const AUTH_ROUTES = [
  "/login",
  "/register",
  "/forgot",
  "/reset",
  "/support",
];

export const LEGAL_ROUTES = [
  "/legal/terms",
  "/legal/privacy",
  "/legal/refunds",
];

export function isPublicRoute(pathname: string): boolean {
  return (
    pathname === "/" ||
    AUTH_ROUTES.includes(pathname) ||
    LEGAL_ROUTES.some((route) => pathname.startsWith(route))
  );
}
