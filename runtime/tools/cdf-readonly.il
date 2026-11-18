; Read-only base CDF summary. Review against local IC617 manual before loading.
; Does not execute callbacks, change cells, save views, or attach technology.
procedure(analogReadBaseCDF(lib cell)
  let((obj base)
    obj = ddGetObj(lib cell)
    unless(obj error("Library/cell not found: %s/%s\n" lib cell))
    base = cdfGetBaseCellCDF(obj)
    unless(base error("Base CDF not found: %s/%s\n" lib cell))
    printf("Base CDF only: %s/%s\n" lib cell)
    foreach(p base~>parameters
      printf("%s type=%L default=%L prompt=%L\n"
        p~>name p~>paramType p~>value p~>prompt)
    )
    t
  )
)
