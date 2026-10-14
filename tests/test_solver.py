import ast
import calendar
import unittest
from pathlib import Path
from solver import solve, validate, build_days, PEOPLE

class SolverTests(unittest.TestCase):
    def test_syntax(self):
        ast.parse(Path("solver.py").read_text(encoding="utf-8"))
    def test_calendar_november(self):
        days=build_days(2026,11,set())
        self.assertEqual(len(days),30)
        self.assertEqual(sum(x["type"]=="sat" for x in days),4)
        self.assertEqual(sum(x["type"]=="weekday" for x in days),20)
        self.assertEqual(sum(x["type"]=="closed" for x in days),6)
    def test_november_2026_160(self):
        data={"year":2026,"month":11,"nominal":160,"closed":[],"locks":{},"weeklyShifts":{}}
        result=solve(data)
        print("NOVEMBER_RESULT",result.get("ok"),result.get("status"),result.get("message"),flush=True)
        self.assertTrue(result.get("ok"),result.get("message"))
        self.assertTrue(result.get("partial"))
        sched=result["schedule"]
        self.assertEqual(set(sched),set(PEOPLE))
        self.assertEqual(validate({**data,"schedule":sched},allow_shortfall=True),[])
        for p in PEOPLE:
            v=sched[p]
            self.assertEqual(len(v),30)
            self.assertLessEqual(sum(x in ("6","18") for x in v),14)
            self.assertLessEqual(abs(v.count("6")-v.count("18")),4)
            for i in range(1,29):
                self.assertFalse(v[i] in ("6","18") and v[i-1] not in ("6","18") and v[i+1] not in ("6","18"))
        self.assertGreater(sum(x["missing"] for x in result["shortfalls"]),0)
        print("NOVEMBER_DISTRIBUTION",{p:(sched[p].count("6"),sched[p].count("18")) for p in PEOPLE},flush=True)
    def test_max_equal_shifts_november(self):
        for shifts in range(14,7,-1):
            data={"year":2026,"month":11,"nominal":shifts*12,"closed":[],"locks":{},"weeklyShifts":{}}
            result=solve(data)
            print("CAPACITY_TEST",shifts,"shifts",shifts*12,"hours",result.get("ok"),result.get("status"),result.get("message"),flush=True)
            if result.get("ok"):
                issues=validate({**data,"schedule":result["schedule"]})
                print("VALIDATION",len(issues),issues[:8],flush=True)
                self.assertEqual(issues,[])
                return
        self.fail("Nie znaleziono grafiku nawet dla 8 zmian na osobę")
    def test_validator_rejects_invalid(self):
        data={"year":2026,"month":11,"nominal":160,"schedule":{p:[""]*30 for p in PEOPLE}}
        issues=validate(data)
        self.assertTrue(issues)
        self.assertTrue(any("wymagane dokładnie" in i for i in issues))
if __name__=="__main__":
    unittest.main(verbosity=2)
