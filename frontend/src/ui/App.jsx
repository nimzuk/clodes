import React, { useState } from 'react'
import useStore from '../useStore.js'
import { Stage, Layer, Image as KImage, Rect } from 'react-konva'

const W=1000,H=1000
function useImage(url){ const [i,set]=React.useState(null); React.useEffect(()=>{ if(!url){set(null);return} const im=new Image(); im.crossOrigin='anonymous'; im.onload=()=>set(im); im.src=url },[url]); return i }
export default function App(){
  const s = useStore()
  const d = s.details[s.active]
  const orderInfo = s.lastOrderInfo
  const img = useImage(d.previewUrl)
  return (
    <div style={{display:'grid',gridTemplateColumns:'280px 1fr',minHeight:'100vh'}}>
      <div style={{padding:16,borderRight:'1px solid #1f2430'}}>
        <div>
          <label>Model</label>
          <select value={s.model} onChange={e=>s.setModel(e.target.value)}>
            <option value="MT">MT</option><option value="WT">WT</option><option value="KT">KT</option>
          </select>
        </div>
        <div style={{margin:'12px 0'}}>
          {['front','sleeveL','back','sleeveR'].map(v=>(
            <button key={v} onClick={()=>s.setActive(v)} style={{marginRight:6, padding:'6px 10px'}}>{v}</button>
          ))}
        </div>
        <div>
          <input type="range" min="0.05" max="4" step="0.01" value={d.transform.scale} onChange={e=>s.setScale(parseFloat(e.target.value))}/>
          <input type="range" min="-1000" max="1000" step="1" value={d.transform.tx} onChange={e=>s.setTx(parseFloat(e.target.value))}/>
          <input type="range" min="-1000" max="1000" step="1" value={d.transform.ty} onChange={e=>s.setTy(parseFloat(e.target.value))}/>
          <div><label><input type="checkbox" checked={d.tile.enabled} onChange={()=>s.toggleTile()}/> tile</label></div>
        </div>
        <div style={{marginTop:12}}>
          <input id="file" type="file" accept="image/png,image/jpeg" style={{display:'none'}} onChange={async (e)=>{ if(!e.target.files?.[0])return; await s.uploadAndSpread(e.target.files[0]); e.target.value='' }}/>
          <label htmlFor="file" style={{padding:'8px 12px',background:'#2563eb',display:'inline-block',borderRadius:8,cursor:'pointer'}}>Upload / Spread</label>
        </div>
        <div style={{marginTop:12}}>
          <button onClick={async ()=>{
            try {
              await s.startOrder()
            } catch (err) {
              console.error(err)
              alert(err.message || String(err))
            }
          }}>Order</button>
        </div>
        {orderInfo?.mockups?.length ? (
          <div style={{marginTop:12, padding:12, border:'1px solid #2563eb', borderRadius:8}}>
            <div style={{fontWeight:600, marginBottom:8}}>Mockups:</div>
            <ul style={{margin:0, paddingLeft:20}}>
              {orderInfo.mockups.map((url, idx)=>(
                <li key={url+idx}><a href={url} target="_blank" rel="noreferrer">{url}</a></li>
              ))}
            </ul>
            {orderInfo.mockups_dir ? (
              <div style={{marginTop:8}}>
                <a href={orderInfo.mockups_dir} target="_blank" rel="noreferrer">Open mockups folder</a>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
      <div style={{display:'grid',placeItems:'center'}}>
        {!img ? <label style={{border:'2px dashed #3a4251',padding:40,borderRadius:12,cursor:'pointer'}}>
          <input type="file" accept="image/png,image/jpeg" style={{display:'none'}} onChange={async (e)=>{ if(!e.target.files?.[0])return; await s.uploadAndSpread(e.target.files[0]); e.target.value='' }}/>
          + Upload image
        </label> : (
          <Stage width={W} height={H}>
            <Layer>
              <Rect x={0} y={0} width={W} height={H} fill="#111318"/>
              <KImage image={img} x={d.transform.tx} y={d.transform.ty} width={img.width*d.transform.scale} height={img.height*d.transform.scale} draggable
                onDragMove={e=>{ const n=e.target; s.setTx(n.x()); s.setTy(n.y()) }}
                onWheel={e=>{ e.evt.preventDefault(); const delta=e.evt.deltaY>0?-0.05:0.05; s.setScale(Math.max(0.05, d.transform.scale+delta)) }}
              />
            </Layer>
          </Stage>
        )}
      </div>
    </div>
  )
}
