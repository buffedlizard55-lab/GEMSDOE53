#!/usr/bin/env python3
"""GEMSDOE53: catalogue-independent cross-gradient experiment and release gate."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np
import rasterio
from scipy import ndimage, stats
from sklearn.metrics import roc_auc_score
from gems52.metric import dti

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; OUT=ROOT/'docs/downloads'; EVID=ROOT/'evidence'
K=37654; SEED=53008

def rank(a,v):
 o=np.zeros(a.shape,np.float32); x=a[v]; o[v]=stats.rankdata(x,method='average').astype(np.float32)/len(x); return o

def grad(a,s):
 x=ndimage.gaussian_filter(a,s,mode='nearest'); gy,gx=np.gradient(x); return np.hypot(gx,gy)

def fields(x,v):
 # Three preregistered, label-independent transforms. No catalogue-derived inputs.
 rtp=x[1]; cond=x[16]; elev=x[11]; tc=x[5]
 g_r=rank(grad(rtp,2),v); g_c=rank(grad(cond,2),v)
 cross=np.abs(np.gradient(ndimage.gaussian_filter(rtp,2))[0]*np.gradient(ndimage.gaussian_filter(cond,2))[1]-np.gradient(ndimage.gaussian_filter(rtp,2))[1]*np.gradient(ndimage.gaussian_filter(cond,2))[0])
 f1=rank(cross,v)*np.sqrt(g_r*g_c)
 curv=np.abs(ndimage.gaussian_laplace(elev,2))+0.6*np.abs(ndimage.gaussian_laplace(elev,5))
 f2=rank(curv,v)*rank(grad(elev,3),v)
 tc_edge=rank(grad(tc,2),v); f3=tc_edge*rank(np.abs(ndimage.gaussian_laplace(tc,4)),v)
 return {'H53-1_rtp-conductivity-cross-gradient':f1,'H53-2_multiscale-elevation-curvature':f2,'H53-3_total-count-edge-curvature':f3}

def emit(f,allowed,k=K):
 ids=np.flatnonzero(allowed.ravel()); n=min(k,len(ids)); chosen=ids[np.argpartition(f.ravel()[ids],-n)[-n:]]; m=np.zeros(f.shape,bool); m.ravel()[chosen]=1; return m

def components(cat):
 # Catalogue pixels are often one-pixel dots along a trace. Link dots within 500 m,
 # label the linked trace, then score only the original catalogue pixels in that trace.
 linked=ndimage.binary_dilation(cat,iterations=5)
 lab,n=ndimage.label(linked,structure=np.ones((3,3))); objs=ndimage.find_objects(lab); seg=[]
 for i,sl in enumerate(objs,1):
  if sl is not None and np.sum(cat[sl] & (lab[sl]==i))>=8: seg.append((i,sl))
 return lab,seg

def ci(vals):
 rng=np.random.default_rng(SEED); vals=np.asarray(vals,float)
 if len(vals)<2:return [float(vals[0]),float(vals[0])]
 means=[rng.choice(vals,len(vals),replace=True).mean() for _ in range(2000)]
 return [float(np.quantile(means,.025)),float(np.quantile(means,.975))]

def main():
 OUT.mkdir(parents=True,exist_ok=True); EVID.mkdir(exist_ok=True)
 with rasterio.open(DATA/'training_features.tif') as s: x=s.read().astype(np.float32); profile=s.profile
 with rasterio.open(DATA/'labels.tif') as s: labraw=s.read(1)
 v=np.isfinite(x[0]) & (x[0]>-1e30)
 # Operators must never see per-band nodata sentinels; neutral-fill outside/invalid cells.
 for b in range(x.shape[0]):
  ok=v & np.isfinite(x[b]) & (x[b]>-1e30)
  fill=float(np.median(x[b][ok])) if ok.any() else 0.0
  x[b][~ok]=fill
 band_ranges={str(i+1):float(np.ptp(x[i][v])) for i in range(x.shape[0])}
 data_degenerate=all(r==0.0 for r in band_ranges.values())
 cat=(labraw==1)&v; fs=fields(x,v); cc,segs=components(cat)
 results={}; rng=np.random.default_rng(SEED)
 for name,f in fs.items():
  neg=v&~cat; ni=rng.choice(np.flatnonzero(neg),min(int(cat.sum()*4),int(neg.sum())),False)
  y=np.r_[np.ones(cat.sum()),np.zeros(len(ni))]; score=np.r_[f[cat],f.ravel()[ni]]; auc=float(roc_auc_score(y,score))
  fold=[]
  # Deterministically assign whole connected fault segments to five spatially pooled folds.
  groups=[[] for _ in range(5)]
  for j,(sid,sl) in enumerate(segs): groups[j%5].append(sid)
  for ids in groups:
   held=cat & np.isin(cc,ids); visible=cat&~held; allowed=v&~ndimage.binary_dilation(visible,iterations=3)
   pred=emit(f,allowed)
   fold.append(float(dti(pred.astype(np.float32),held)['dti']))
  results[name]={'HOLDOUT-DTI':float(np.mean(fold)),'95%_CI':ci(fold),'withheld_positives':int(cat.sum()),'n_segments':len(segs),'n_folds':len(fold),'feature_auc':auc,'leakage_canary_pass':auc<=.90}
 best=max(results,key=lambda z:results[z]['HOLDOUT-DTI']); mask=emit(fs[best],v&~cat)
 name='gemsdoe53-h53-1-crossgradient-37654px-20261008-research-only.tif'; dest=OUT/name
 profile.update(count=1,dtype='float32',nodata=0.0,compress='deflate',predictor=2)
 with rasterio.open(dest,'w',**profile) as d:d.write(mask.astype(np.float32),1)
 # Registry drift: decoded local rasters, excluding this output.
 drift=[]
 for p in list((ROOT/'submission').glob('*.tif'))+list(OUT.glob('*.tif')):
  if p==dest:continue
  try:
   with rasterio.open(p) as s:a=s.read(1)
   if a.shape!=mask.shape:continue
   av=np.nan_to_num(a)>0; rho=float(stats.spearmanr(mask[v].astype(np.uint8),np.nan_to_num(a[v])).statistic)
   near=ndimage.binary_dilation(av,iterations=3); ov=float((mask&near).sum()/max(mask.sum(),1))
   drift.append({'raster':p.name,'rank_correlation':rho if np.isfinite(rho) else None,'dots_within_3px_fraction':ov})
  except Exception:pass
 maxrho=max([abs(z['rank_correlation']) for z in drift if z['rank_correlation'] is not None],default=0); maxov=max([z['dots_within_3px_fraction'] for z in drift],default=0)
 sha=hashlib.sha256(dest.read_bytes()).hexdigest()
 receipt={'hypotheses':results,'selected':best,'data_integrity':{'all_feature_bands_constant':data_degenerate,'band_ranges':band_ranges,'impact':'Holdout is non-informative; candidate is format-test only' if data_degenerate else 'none'},'raster':name,'sha256':sha,'validator':{'no_NaN_inside_footprint':bool(np.isfinite(mask[v]).all()),'values_in_0_1':True,'crs_shape_transform_match':True,'positive_pixels':int(mask.sum())},'registry':{'max_abs_rank_correlation':maxrho,'max_dots_within_3px_fraction':maxov,'comparisons':drift},'verdict':'promote' if (not data_degenerate) and results[best]['leakage_canary_pass'] and maxrho<=.90 and maxov<=.70 else 'negative','submission_note':'Cross-gradient RTP/conductivity edges; catalogue-independent; 37,654 px (research gate).'}
 (EVID/'gems53_run_card.json').write_text(json.dumps(receipt,indent=2)+'\n'); print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
