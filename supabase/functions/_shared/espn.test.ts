import { espnLiveScoreboardDates } from "./espn.ts";

function check(value:unknown, message:string):asserts value {
  if (!value) throw new Error(message);
}

Deno.test("Midnight UTC: ESPN must read previous AND current calendar day",()=>{
  const dates=espnLiveScoreboardDates(new Date("2026-10-14T01:53:00Z"));
  check(dates.length===2,"Both dates required");
  check(dates[0]==="20261013"&&dates[1]==="20261014","Wrong cross-midnight calendar dates");
});

Deno.test("Late daytime UTC: ESPN reads current calendar only",()=>{
  const dates=espnLiveScoreboardDates(new Date("2026-10-14T14:00:00Z"));
  check(dates.length===1&&dates[0]==="20261014","Expected only current date");
});

Deno.test("Year boundary: previous day is previous year",()=>{
  const dates=espnLiveScoreboardDates(new Date("2027-01-01T02:00:00Z"));
  check(dates[0]==="20261231"&&dates[1]==="20270101","Year crossover broken");
});
