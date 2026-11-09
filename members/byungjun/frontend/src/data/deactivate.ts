import { indicators } from "./indicators";

// "부채비율은 사용하고 싶지 않아", "PER 버려줘", "배당수익률 삭제해줘", "영업이익은 비활성화해줘" 같은
// 지표를 비활성화(기본값으로 되돌림)하려는 말을 찾는다. 모델에 보내지 않고 화면에서 바로 처리한다.
// "빚 많은 회사는 제외할래요"처럼 조건을 정하는 말은 지표 이름이 없거나 아래 표현이 없어서 걸리지 않는다.
const INTENT =
  /사용 ?(하고 ?싶지 ?않|하지 ?않|하지 ?말|안 ?할|안 ?해|안 ?쓸)|쓰(고 ?싶지 ?않|지 ?않|지 ?말|기 ?싫|지 ?마)|안 ?쓸|버려|버릴|삭제|비활성|없애|지워|필요 ?없|꺼 ?줘|끌래|보지 ?않|안 ?볼/;

// 지표 이름 말고 자주 쓰는 다른 말
export const ALIASES: Record<number, string[]> = {
  3: ["ebitda", "이자보상"],
  5: ["영업이익"],
  6: ["영업흑자연수", "연속영업흑자", "연속흑자"],
  10: ["per"],
  11: ["pbr"],
  12: ["배당수익률", "배당률"],
  13: ["연속배당", "배당연수"],
  14: ["시총"],
  16: ["52주고점", "고점대비"],
  17: ["52주저점", "저점대비"],
  18: ["변동성"],
  19: ["평균거래대금", "거래대금"],
  20: ["거래량증가", "거래량배율"],
};

const norm = (s: string) => s.replace(/\s/g, "").toLowerCase();

// 지표를 비활성화하라는 말이면 그 말에 나온 지표 id들을, 아니면 null
export function findDeactivation(text: string): number[] | null {
  if (!INTENT.test(text)) return null;
  const keys = indicators
    .flatMap((i) => [i.name, ...(ALIASES[i.id] ?? [])].map((k) => ({ id: i.id, key: norm(k) })))
    .sort((a, b) => b.key.length - a.key.length); // 긴 이름 먼저: "영업이익 증가율"이 "영업이익"에 먼저 잡히게
  let rest = norm(text);
  const ids: number[] = [];
  for (const { id, key } of keys) {
    if (rest.includes(key)) {
      if (!ids.includes(id)) ids.push(id);
      rest = rest.replace(key, "#");
    }
  }
  return ids.length > 0 ? ids : null;
}
