// 앱을 켰을 때 처음 보이는 화면 설정 (이 기기의 localStorage에 저장한다)
export const HOME_OPTIONS = [
  { to: "/", label: "원칙 생성" },
  { to: "/principles", label: "원칙 관리" },
  { to: "/stocks", label: "종목 검색" },
  { to: "/sim", label: "시뮬레이션" },
];

const HOME_KEY = "srk-home";
const ADMIN_KEY = "srk-admin";

export function getHome(): string {
  const saved = localStorage.getItem(HOME_KEY);
  return HOME_OPTIONS.some((o) => o.to === saved) ? saved! : "/stocks";
}

export function setHome(to: string) {
  localStorage.setItem(HOME_KEY, to);
}

export function getAdmin(): boolean {
  return localStorage.getItem(ADMIN_KEY) === "on";
}

export function setAdmin(on: boolean) {
  localStorage.setItem(ADMIN_KEY, on ? "on" : "off");
}
