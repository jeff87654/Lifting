
LogTo("C:/Users/jeffr/Downloads/Lifting/quick_test2.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
allPass := true;
known := rec(); known.2:=2; known.3:=4; known.4:=11; known.5:=19; known.6:=56; known.7:=96; known.8:=296;
for n in [2..8] do
    count := CountAllConjugacyClassesFast(n);
    if count = known.(n) then Print("S_",n,"=",count," PASS
");
    else Print("S_",n,"=",count," FAIL (expected ",known.(n),")
"); allPass:=false; fi;
od;
if allPass then Print("ALL PASS
"); else Print("FAILURES
"); fi;
LogTo(); QUIT;
