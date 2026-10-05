# ACS Load Calculator V5

The calculator keeps the entered carton height upright and allows only a 90°
length/width rotation on each layer. V5 retains the fast V4 guillotine solver
and uses OR-Tools CP-SAT only when the area bound leaves room to improve.

## Run locally

```powershell
python -m pip install -r requirements.txt
npm install
npm start
```

Open <http://127.0.0.1:4173>. The local Python service is required for V5;
the browser worker intentionally does not fall back to the less capable V4
solver.

## Validate

```powershell
npm test
npm run build
```

The supplied historical pallet expectations for 220×290×380, 220×220×230,
1000×400×120, and 1000×360×230 conflict with the explicit upright-height
rule. The regression suite documents and tests the physically valid upright
results instead of hard-coding or tipping those cartons.
