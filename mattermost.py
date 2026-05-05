#!/usr/bin/env python3
"""
Mattermost Backup Viewer — serwer Python
Zastępuje mattermost.php; uruchom z tego samego folderu co results/

Wymagania: tylko biblioteka standardowa (Python 3.7+)

Użycie:
    python server.py              # http://localhost:8080
    python server.py 9000         # inny port
    python server.py 8080 ./dane  # inny port i inny katalog results/
"""

import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ── Konfiguracja ─────────────────────────────────────────────────────────────
PORT         = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
RESULTS_DIR  = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("results")
SEARCH_LIMIT = 200

MEDIA_EXTS = {
    "png","jpg","jpeg","gif","webp","svg","bmp","tiff","tif",
    "mp4","webm","ogg","mov","mkv",
}

# ── HTML viewer (przepisany z PHP — identyczny wygląd) ───────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mattermost Backup Viewer</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
  :root{--bg:#0f1117;--surface:#181c27;--surface2:#1e2335;--border:#2a3050;--accent:#4f8ef7;--accent2:#7c3aed;--green:#22c55e;--yellow:#f59e0b;--red:#ef4444;--text:#e2e8f0;--text2:#8892aa;--text3:#4a5568;--mono:'IBM Plex Mono',monospace;--sans:'IBM Plex Sans',sans-serif;--sidebar-w:260px}
  :root.light{--bg:#f5f7fa;--surface:#ffffff;--surface2:#eef1f6;--border:#d0d7e3;--accent:#2563eb;--green:#16a34a;--yellow:#d97706;--red:#dc2626;--text:#1e2533;--text2:#4b5671;--text3:#9aa3b5}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:var(--sans);background:var(--bg);color:var(--text);height:100vh;overflow:hidden;display:flex;flex-direction:column}
  #drop-screen{flex:1;display:none;flex-direction:column;align-items:center;justify-content:center;gap:2rem;padding:2rem}
  #drop-screen.visible{display:flex}
  #drop-screen.hidden{display:none}
  .logo{font-family:var(--mono);font-size:1rem;color:var(--accent);letter-spacing:.2em;text-transform:uppercase;opacity:.7}
  .drop-zone{border:2px dashed var(--border);border-radius:16px;padding:4rem 6rem;text-align:center;cursor:pointer;transition:border-color .2s,background .2s;position:relative;background:var(--surface)}
  .drop-zone:hover,.drop-zone.over{border-color:var(--accent);background:#1a2040}
  .drop-zone h2{font-size:1.4rem;font-weight:500;margin-bottom:.5rem}
  .drop-zone p{color:var(--text2);font-size:.9rem}
  .drop-zone input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer}
  .msg-images{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.6rem}
  .msg-img{max-width:320px;max-height:240px;border-radius:8px;border:1px solid var(--border);cursor:zoom-in;object-fit:cover;transition:opacity .2s}
  .msg-img:hover{opacity:.85}
  .msg-video{max-width:480px;max-height:300px;border-radius:8px;border:1px solid var(--border);background:#000;display:block}
  #lightbox{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:1000;align-items:center;justify-content:center;cursor:zoom-out}
  #lightbox.open{display:flex}
  #lightbox img{max-width:92vw;max-height:92vh;border-radius:10px;box-shadow:0 8px 60px rgba(0,0,0,.8)}
  #lightbox-close{position:fixed;top:1.2rem;right:1.5rem;color:#fff;font-size:1.8rem;cursor:pointer;opacity:.7;line-height:1}
  #lightbox-close:hover{opacity:1}
  .folder-hint{font-size:.72rem;color:var(--text3);font-family:var(--mono);margin-top:.3rem}
  .folder-btn{display:inline-flex;align-items:center;gap:.4rem;background:none;border:1px solid var(--border);color:var(--text2);border-radius:6px;padding:.25rem .7rem;font-size:.75rem;cursor:pointer;transition:border-color .2s,color .2s;font-family:var(--mono);margin-left:.4rem}
  .folder-btn:hover{border-color:var(--accent);color:var(--accent)}
  .drop-icon{font-size:3rem;margin-bottom:1rem;display:block}
  #app{display:none;flex:1;overflow:hidden;height:100vh}
  #app.visible{display:flex}
  aside{width:var(--sidebar-w);min-width:160px;max-width:600px;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;position:relative;flex-shrink:0}
  #sidebar-resizer{position:absolute;top:0;right:0;width:5px;height:100%;cursor:col-resize;z-index:10;background:transparent;transition:background .15s}
  #sidebar-resizer:hover,#sidebar-resizer.dragging{background:var(--accent);opacity:.5}
  .sidebar-header{padding:1rem 1.2rem .8rem;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;gap:.5rem}
  .sidebar-header h1{font-family:var(--mono);font-size:.75rem;color:var(--accent);letter-spacing:.15em;text-transform:uppercase}
  .new-btn{background:none;border:1px solid var(--border);color:var(--text2);border-radius:6px;padding:.25rem .6rem;font-size:.75rem;cursor:pointer;transition:border-color .2s,color .2s;font-family:var(--mono)}
  .new-btn:hover{border-color:var(--accent);color:var(--accent)}
  .search-wrap{padding:.6rem .8rem;border-bottom:1px solid var(--border)}
  .search-wrap input{width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:.45rem .8rem;color:var(--text);font-size:.82rem;font-family:var(--sans);outline:none;transition:border-color .2s}
  .search-wrap input:focus{border-color:var(--accent)}
  .search-wrap input::placeholder{color:var(--text3)}
  #channel-list{overflow-y:auto;flex:1;padding:.4rem 0}
  #channel-list::-webkit-scrollbar{width:4px}
  #channel-list::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
  .ch-item{display:flex;align-items:center;gap:.6rem;padding:.5rem 1.2rem;cursor:pointer;border-left:3px solid transparent;transition:background .15s}
  .ch-item:hover{background:var(--surface2)}
  .ch-item.active{background:#1a2040;border-left-color:var(--accent)}
  :root.light .ch-item.active{background:#e8edf8}
  .ch-icon{font-size:.85rem;opacity:.5;flex-shrink:0;width:16px;text-align:center}
  .ch-info{flex:1;min-width:0}
  .ch-name{font-size:.85rem;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .ch-meta{font-size:.7rem;color:var(--text3);font-family:var(--mono)}
  .ch-group-header{display:flex;align-items:center;gap:.4rem;padding:.7rem 1.2rem .25rem;font-size:.65rem;font-family:var(--mono);font-weight:600;color:var(--text3);letter-spacing:.1em;text-transform:uppercase;cursor:pointer;user-select:none;transition:color .15s}
  .ch-group-header:hover{color:var(--text2)}
  .ch-group-count{margin-left:auto;font-weight:400;opacity:.7}
  .ch-group-arrow{font-size:.55rem;transition:transform .2s}
  .ch-group-header.collapsed .ch-group-arrow{transform:rotate(-90deg)}
  .ch-group-body.collapsed{display:none}
  .sidebar-footer{padding:.6rem 1.2rem;border-top:1px solid var(--border);font-size:.7rem;color:var(--text3);font-family:var(--mono);display:flex;flex-direction:column;gap:.4rem}
  .sidebar-footer-actions{display:flex;align-items:center;justify-content:space-between}
  .sidebar-footer a{color:var(--text3);text-decoration:none;transition:color .15s}
  .sidebar-footer a:hover{color:var(--accent)}
  .theme-toggle{background:none;border:1px solid var(--border);border-radius:6px;color:var(--text2);font-size:.7rem;font-family:var(--mono);padding:.2rem .5rem;cursor:pointer;transition:border-color .2s,color .2s}
  .theme-toggle:hover{border-color:var(--accent);color:var(--accent)}
  main{flex:1;min-height:0;display:flex;flex-direction:column;overflow:hidden}
  .topbar{padding:.85rem 1.5rem;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--surface);flex-shrink:0}
  .topbar-left{display:flex;align-items:center;gap:.8rem}
  .topbar-icon{font-size:1rem;opacity:.4}
  .topbar h2{font-size:1rem;font-weight:600}
  .topbar-meta{font-size:.75rem;color:var(--text2);font-family:var(--mono)}
  .topbar-right{display:flex;align-items:center;gap:.6rem}
  .badge{background:var(--surface2);border:1px solid var(--border);border-radius:100px;padding:.2rem .65rem;font-size:.7rem;font-family:var(--mono);color:var(--text2)}
  .filter-bar{padding:.5rem 1.5rem;border-bottom:1px solid var(--border);display:flex;gap:.5rem;align-items:center;background:var(--bg);flex-shrink:0}
  .filter-bar input{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:.35rem .8rem;color:var(--text);font-size:.8rem;font-family:var(--sans);outline:none;transition:border-color .2s;flex:1}
  .filter-bar input:focus{border-color:var(--accent)}
  .filter-bar input::placeholder{color:var(--text3)}
  .filter-bar label{font-size:.75rem;color:var(--text2);white-space:nowrap}
  #messages{flex:1 1 0;height:0;overflow-y:auto;padding:1rem 1.5rem 2rem}
  #messages::-webkit-scrollbar{width:5px}
  #messages::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
  .empty-state{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:.8rem;color:var(--text3);font-family:var(--mono);font-size:.85rem}
  .empty-state span{font-size:2.5rem}
  .date-divider{display:flex;align-items:center;gap:.8rem;margin:1.5rem 0 .8rem;color:var(--text3);font-size:.72rem;font-family:var(--mono)}
  .date-divider::before,.date-divider::after{content:'';flex:1;height:1px;background:var(--border)}
  .msg{display:flex;gap:.9rem;padding:.5rem .6rem;border-radius:8px;transition:background .1s;position:relative}
  .msg:hover{background:var(--surface)}
  .msg.reply{margin-left:2rem;border-left:2px solid var(--border);padding-left:1rem;opacity:.85}
  .msg.reply:hover{opacity:1}
  .avatar{width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-family:var(--mono);font-size:.8rem;font-weight:600;flex-shrink:0;margin-top:2px}
  .msg-body{flex:1;min-width:0}
  .msg-header{display:flex;align-items:baseline;gap:.5rem;margin-bottom:.2rem}
  .msg-author{font-weight:600;font-size:.88rem}
  .msg-time{font-size:.7rem;color:var(--text3);font-family:var(--mono)}
  .msg-text{font-size:.88rem;line-height:1.6;color:var(--text);word-break:break-word;white-space:pre-wrap}
  .msg-text code{background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:.1em .4em;font-family:var(--mono);font-size:.82em;color:#a5b4fc}
  .msg-text pre{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:.9rem 1rem;overflow-x:auto;margin-top:.4rem;font-family:var(--mono);font-size:.8rem;color:#a5b4fc;line-height:1.5}
  .msg-text pre code{background:none;border:none;padding:0;font-size:inherit}
  .msg-table{border-collapse:collapse;margin-top:.5rem;font-size:.82rem;max-width:100%;overflow-x:auto;display:block}
  .msg-table th,.msg-table td{border:1px solid var(--border);padding:.35rem .7rem;text-align:left;white-space:nowrap}
  .msg-table th{background:var(--surface2);font-weight:600;font-family:var(--mono);font-size:.78rem;color:var(--text2)}
  .msg-table tr:nth-child(even) td{background:var(--surface)}
  .msg-table tr:hover td{background:var(--surface2)}
  .msg-files{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.5rem}
  .file-chip{display:flex;align-items:center;gap:.3rem;background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:.25rem .6rem;font-size:.75rem;font-family:var(--mono);color:var(--text2)}
  .reply-badge{display:inline-flex;align-items:center;gap:.3rem;font-size:.7rem;color:var(--text3);font-family:var(--mono);margin-bottom:.2rem}
  mark{background:rgba(79,142,247,.3);color:var(--text);border-radius:2px;padding:0 1px}
  .no-channel{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1rem;color:var(--text3);font-family:var(--mono);font-size:.85rem}
  .no-channel span{font-size:3rem}
  #global-search-bar{display:flex;align-items:center;gap:.6rem;padding:.6rem 1rem;background:var(--surface);border-bottom:1px solid var(--border);flex-shrink:0}
  #global-search-bar input{flex:1;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:.45rem .9rem;color:var(--text);font-size:.85rem;font-family:var(--sans);outline:none;transition:border-color .2s}
  #global-search-bar input:focus{border-color:var(--accent)}
  #global-search-bar input::placeholder{color:var(--text3)}
  .gsearch-btn{background:var(--accent);border:none;border-radius:8px;color:#fff;padding:.45rem .9rem;font-size:.82rem;font-family:var(--mono);cursor:pointer;white-space:nowrap;transition:opacity .2s}
  .gsearch-btn:hover{opacity:.85}
  .gsearch-btn:disabled{opacity:.4;cursor:default}
  #global-results{flex:1 1 0;height:0;overflow-y:auto;padding:.5rem 1.5rem 2rem}
  #global-results::-webkit-scrollbar{width:5px}
  #global-results::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
  .gr-item{padding:.7rem .8rem;border-radius:8px;border-left:3px solid var(--border);margin-bottom:.4rem;cursor:pointer;transition:background .15s,border-color .15s}
  .gr-item:hover{background:var(--surface);border-left-color:var(--accent)}
  .gr-channel{font-size:.7rem;font-family:var(--mono);color:var(--accent);margin-bottom:.25rem}
  .gr-meta{font-size:.72rem;color:var(--text3);font-family:var(--mono);margin-bottom:.3rem}
  .gr-text{font-size:.85rem;color:var(--text);line-height:1.5;white-space:pre-wrap;word-break:break-word}
  .gr-more{text-align:center;padding:.8rem;font-size:.75rem;font-family:var(--mono);color:var(--text3)}
  .tab-bar{display:flex;border-bottom:1px solid var(--border);background:var(--surface);flex-shrink:0}
  .tab{padding:.6rem 1.2rem;font-size:.8rem;font-family:var(--mono);color:var(--text2);cursor:pointer;border-bottom:2px solid transparent;transition:color .15s,border-color .15s;user-select:none}
  .tab:hover{color:var(--text)}
  .tab.active{color:var(--accent);border-bottom-color:var(--accent)}
  .pinned-badge{display:inline-block;background:var(--surface2);border-radius:100px;padding:.05em .45em;font-size:.75em;margin-left:.3em;color:var(--yellow)}
</style>
</head>
<body>
<div id="drop-screen">
  <div class="logo">⬡ Mattermost Backup Viewer</div>
  <div class="drop-zone" id="drop-zone">
    <span class="drop-icon">📂</span>
    <h2>Wrzuć folder z backupem</h2>
    <p>Wybierz np. <code style="color:var(--accent);font-size:.85em">results/20260504/</code><br>
    aby załadować wszystkie kanały i grafiki naraz</p>
    <input type="file" id="file-input" webkitdirectory multiple>
  </div>
  <p style="color:var(--text3);font-size:.78rem;font-family:var(--mono)">
    Możesz też wrzucić pojedynczy folder kanału lub przeciągnąć go tutaj
  </p>
</div>
<div id="app">
  <aside>
    <div id="sidebar-resizer"></div>
    <div class="sidebar-header">
      <h1>⬡ Kanały</h1>
      <div style="display:flex;gap:.4rem">
        <button class="new-btn" id="add-more">+ dodaj</button>
        <button class="new-btn" id="clear-btn" title="Wyczyść zapisane dane" style="color:var(--red);border-color:var(--red);opacity:.6">✕</button>
      </div>
    </div>
    <div class="search-wrap">
      <input type="text" id="ch-search" placeholder="Szukaj kanału…">
    </div>
    <div id="channel-list"></div>
    <div class="sidebar-footer">
      <div class="sidebar-footer-stats" id="sidebar-footer"></div>
      <div class="sidebar-footer-actions">
        <a href="https://github.com/lukaszmarcola/mattermost_backup" target="_blank" rel="noopener">⬡ GitHub</a>
        <button class="theme-toggle" id="theme-toggle" onclick="toggleTheme()">☀ Light</button>
      </div>
    </div>
  </aside>
  <main id="main-area">
    <div id="global-search-bar">
      <input type="text" id="global-input" placeholder="🔍 Szukaj we wszystkich kanałach… (min. 2 znaki, Enter)">
      <button class="gsearch-btn" id="global-btn">Szukaj</button>
    </div>
    <div id="global-view" style="display:none;flex-direction:column;flex:1;min-height:0;overflow:hidden;">
      <div class="topbar">
        <div class="topbar-left">
          <span class="topbar-icon">🔍</span>
          <div>
            <h2 id="gr-title">Wyniki wyszukiwania</h2>
            <div class="topbar-meta" id="gr-meta"></div>
          </div>
        </div>
        <div class="topbar-right">
          <button class="new-btn" id="gr-close">✕ zamknij</button>
        </div>
      </div>
      <div id="global-results"></div>
    </div>
    <div class="no-channel" id="no-channel">
      <span>💬</span>
      Wybierz kanał z listy
    </div>
    <div id="channel-view" style="display:none;flex-direction:column;flex:1;min-height:0;overflow:hidden;">
      <div class="topbar">
        <div class="topbar-left">
          <span class="topbar-icon" id="tb-icon"></span>
          <div>
            <h2 id="tb-title"></h2>
            <div class="topbar-meta" id="tb-meta"></div>
          </div>
        </div>
        <div class="topbar-right">
          <span class="badge" id="tb-count"></span>
          <button class="folder-btn" id="load-folder-btn" title="Wczytaj folder z grafikami">📁 grafiki</button>
        </div>
      </div>
      <div class="tab-bar">
        <div class="tab active" id="tab-all" onclick="switchTab('all')">All messages</div>
        <div class="tab" id="tab-pinned" onclick="switchTab('pinned')">📌 Pinned <span class="pinned-badge" id="pinned-count">0</span></div>
      </div>
      <div class="filter-bar" id="filter-bar">
        <label>🔍</label>
        <input type="text" id="msg-search" placeholder="Search messages…">
        <label style="margin-left:.5rem">from:</label>
        <input type="text" id="filter-user" placeholder="username" style="flex:0;width:130px">
      </div>
      <div id="messages"></div>
    </div>
  </main>
</div>
<input type="file" id="add-file-input" webkitdirectory multiple style="display:none">
<input type="file" id="folder-input" webkitdirectory multiple style="display:none">
<div id="lightbox">
  <span id="lightbox-close">✕</span>
  <img id="lightbox-img" src="" alt="">
</div>
<script>
const state={channels:[],active:null,images:{}};
const STORAGE_KEY='mm_backup_channels';

function saveToStorage(){
  try{localStorage.setItem(STORAGE_KEY,JSON.stringify(state.channels.map(c=>({meta:c.meta,posts:c.posts}))))}
  catch(e){console.warn('[backup] localStorage pełne:',e.message);showToast('⚠ Za dużo danych — nie zapisano lokalnie')}
}

function loadFromStorage(){
  try{const raw=localStorage.getItem(STORAGE_KEY);if(!raw)return false;const ch=JSON.parse(raw);if(!ch.length)return false;state.channels=ch;return true}
  catch(e){console.warn('[backup] Błąd odczytu:',e);return false}
}

function clearStorage(){
  localStorage.removeItem(STORAGE_KEY);state.channels=[];state.active=null;state.images={};
  document.getElementById('drop-screen').classList.add('visible');
  document.getElementById('app').classList.remove('visible');
  showToast('Wyczyszczono zapisane dane');
}

const PALETTE=[['#1e3a5f','#4f8ef7'],['#1a2e1a','#22c55e'],['#2d1b4e','#a78bfa'],['#3b1f1f','#f87171'],['#2a2010','#f59e0b'],['#0f2a2a','#2dd4bf'],['#2a1030','#e879f9'],['#1e2a3b','#60a5fa']];
function avatarStyle(name){let h=0;for(const c of name)h=(h*31+c.charCodeAt(0))&0xffffffff;const[bg,fg]=PALETTE[Math.abs(h)%PALETTE.length];return`background:${bg};color:${fg}`}
function initials(name){return name.split(/[\s._-]/).filter(Boolean).slice(0,2).map(p=>p[0].toUpperCase()).join('')||'?'}
function chIcon(type){return{O:'#',P:'🔒',D:'@',G:'⊕'}[type]||'#'}

const IMG_EXTS=new Set(['png','jpg','jpeg','gif','webp','svg','bmp','tiff','tif']);
const VID_EXTS=new Set(['mp4','webm','ogg','mov','mkv']);
function isImage(name){return IMG_EXTS.has(name.split('.').pop().toLowerCase())}
function isVideo(name){return VID_EXTS.has(name.split('.').pop().toLowerCase())}

function showToast(msg){
  let t=document.getElementById('toast');
  if(!t){t=document.createElement('div');t.id='toast';t.style.cssText=`position:fixed;bottom:1.5rem;right:1.5rem;background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:.5rem 1rem;border-radius:8px;font-family:var(--mono);font-size:.75rem;z-index:999;transition:opacity .3s`;document.body.appendChild(t)}
  t.textContent=msg;t.style.opacity='1';clearTimeout(t._timer);t._timer=setTimeout(()=>t.style.opacity='0',2500);
}

function loadFiles(files){
  const jsonFiles=Array.from(files).filter(f=>f.name.endsWith('.json'));
  const imgFiles=Array.from(files).filter(f=>isImage(f.name)||isVideo(f.name));
  for(const file of imgFiles){if(state.images[file.name])URL.revokeObjectURL(state.images[file.name]);state.images[file.name]=URL.createObjectURL(file)}
  if(!jsonFiles.length){if(imgFiles.length){renderMessages();showToast(`Wczytano ${imgFiles.length} grafik`)}else showToast('Nie znaleziono pliku .json ani grafik');return}
  let loaded=0;
  for(const file of jsonFiles){
    const r=new FileReader();
    r.onload=e=>{
      try{
        const data=JSON.parse(e.target.result);
        const entries=Array.isArray(data)?data:[data];
        for(const entry of entries){
          if(!entry.channel||!entry.posts)throw new Error('Nieprawidłowy format');
          const exists=state.channels.findIndex(c=>c.meta.id===entry.channel.id);
          if(exists>=0)state.channels[exists]={meta:entry.channel,posts:entry.posts};
          else state.channels.push({meta:entry.channel,posts:entry.posts});
        }
      }catch(err){alert(`Błąd w pliku ${file.name}: ${err.message}`)}
      loaded++;
      if(loaded===jsonFiles.length){saveToStorage();renderSidebar();if(imgFiles.length)showToast(`Wczytano kanał + ${imgFiles.length} grafik`)}
    };
    r.readAsText(file,'utf-8');
  }
}

const collapsedGroups=new Set(JSON.parse(localStorage.getItem('mm_collapsed')||'[]'));
function saveCollapsed(){localStorage.setItem('mm_collapsed',JSON.stringify([...collapsedGroups]))}

function renderSidebar(){
  document.getElementById('drop-screen').classList.add('hidden');
  document.getElementById('app').classList.add('visible');
  const q=document.getElementById('ch-search').value.toLowerCase();
  const list=document.getElementById('channel-list');
  list.innerHTML='';
  const filtered=state.channels.filter(ch=>ch.meta.display_name.toLowerCase().includes(q));
  const groups=[
    {key:'channels',label:'Channels',icon:'#',types:new Set(['O','P','?'])},
    {key:'groups',label:'Group messages',icon:'⊕',types:new Set(['G'])},
    {key:'dms',label:'Direct messages',icon:'@',types:new Set(['D'])},
  ];
  groups.forEach(group=>{
    const items=filtered.filter(ch=>group.types.has(ch.meta.type));
    if(!items.length)return;
    const isCollapsed=collapsedGroups.has(group.key);
    const header=document.createElement('div');
    header.className='ch-group-header'+(isCollapsed?' collapsed':'');
    header.innerHTML=`<span class="ch-group-arrow">▾</span><span>${group.icon} ${group.label}</span><span class="ch-group-count">${items.length}</span>`;
    header.onclick=()=>{const body=header.nextElementSibling;const col=header.classList.toggle('collapsed');body.classList.toggle('collapsed',col);if(col)collapsedGroups.add(group.key);else collapsedGroups.delete(group.key);saveCollapsed()};
    list.appendChild(header);
    const body=document.createElement('div');
    body.className='ch-group-body'+(isCollapsed?' collapsed':'');
    items.forEach(ch=>{
      const realIdx=state.channels.indexOf(ch);
      const div=document.createElement('div');
      div.className='ch-item'+(realIdx===state.active?' active':'');
      const count=ch.posts===null?(ch.postCount!==null?ch.postCount+' msg':'…'):ch.posts.length+' msg';
      div.innerHTML=`<span class="ch-icon">${chIcon(ch.meta.type)}</span><div class="ch-info"><div class="ch-name">${esc(ch.meta.display_name)}</div><div class="ch-meta">${count}</div></div>`;
      div.onclick=()=>openChannel(realIdx);
      body.appendChild(div);
    });
    list.appendChild(body);
  });
  const total=state.channels.reduce((s,c)=>s+(c.posts?c.posts.length:c.postCount||0),0);
  document.getElementById('sidebar-footer').textContent=`${state.channels.length} channels · ${total} msg`;
}

async function openChannel(idx){
  state.active=idx;renderSidebar();
  const ch=state.channels[idx];
  document.getElementById('no-channel').style.display='none';
  const view=document.getElementById('channel-view');
  view.style.display='flex';
  document.getElementById('tb-icon').textContent=chIcon(ch.meta.type);
  document.getElementById('tb-title').textContent=ch.meta.display_name;
  document.getElementById('tb-meta').textContent='';
  document.getElementById('tb-count').textContent='Ładuję…';
  document.getElementById('messages').innerHTML='<div class="empty-state"><span>⏳</span>Ładuję wiadomości…</div>';
  document.getElementById('msg-search').value='';
  document.getElementById('filter-user').value='';
  activeTab='all';
  document.getElementById('tab-all').classList.add('active');
  document.getElementById('tab-pinned').classList.remove('active');
  document.getElementById('filter-bar').style.display='';
  await ensurePostsLoaded(idx);
  document.getElementById('tb-icon').textContent=chIcon(ch.meta.type);
  document.getElementById('tb-title').textContent=ch.meta.display_name;
  document.getElementById('tb-meta').textContent=`${ch.meta.team?ch.meta.team+' · ':''}eksport: ${(ch.meta.exported_at||'').slice(0,10)||'?'}`;
  document.getElementById('tb-count').textContent=`${(ch.posts||[]).length} wiadomości`;
  renderMessages();
}

let activeTab='all';
function switchTab(tab){
  activeTab=tab;
  document.getElementById('tab-all').classList.toggle('active',tab==='all');
  document.getElementById('tab-pinned').classList.toggle('active',tab==='pinned');
  document.getElementById('filter-bar').style.display=tab==='pinned'?'none':'';
  renderMessages();
}

const CHUNK=100;
let vState={posts:[],offset:0,sentinel:null};

let _searchTimer=null;
function renderMessages(){
  if(state.active===null)return;
  const ch=state.channels[state.active];
  if(!ch.posts)return;
  const folder=ch.folder||null;
  const q=document.getElementById('msg-search').value.toLowerCase().trim();
  const userQ=document.getElementById('filter-user').value.toLowerCase().trim();
  const pinnedAll=ch.posts.filter(p=>!!p.pinned);
  const pinnedCountEl=document.getElementById('pinned-count');
  if(pinnedCountEl)pinnedCountEl.textContent=pinnedAll.length;
  let filtered=ch.posts.filter(p=>{
    if(activeTab==='pinned')return!!p.pinned;
    if(userQ&&!(p.username||'').toLowerCase().includes(userQ))return false;
    if(q&&!(p.message||'').toLowerCase().includes(q))return false;
    return true;
  });
  const container=document.getElementById('messages');
  if(vState.scrollHandler)container.removeEventListener('scroll',vState.scrollHandler);
  container.innerHTML='';
  if(!filtered.length){container.innerHTML='<div class="empty-state"><span>🔍</span>Brak wyników</div>';vState={posts:[],offset:0,folder,q,scrollHandler:null};return}
  const handler=()=>{if(container.scrollTop<400)prependChunk(container)};
  vState={posts:filtered,offset:0,folder,q,scrollHandler:handler};
  prependChunk(container);
  container.scrollTop=container.scrollHeight;
  container.addEventListener('scroll',handler);
}

function prependChunk(container){
  const{posts,offset,folder,q}=vState;
  if(offset>=posts.length)return;
  const total=posts.length;
  const endIdx=total-offset;
  const startIdx=Math.max(0,endIdx-CHUNK);
  const batch=posts.slice(startIdx,endIdx);
  const prevHeight=container.scrollHeight;
  const prevTop=container.scrollTop;
  const frag=document.createDocumentFragment();
  const newOffset=offset+batch.length;
  if(newOffset>=total){const info=document.createElement('div');info.className='empty-state';info.style.cssText='padding:1.5rem;font-size:.75rem';info.textContent=`── ${total} messages ──`;frag.appendChild(info)}
  let lastDate='';
  for(let i=0;i<batch.length;i++){
    const post=batch[i];
    const d=(post.created||'').slice(0,10);
    if(d&&d!==lastDate){const div=document.createElement('div');div.className='date-divider';div.textContent=formatDate(d);frag.appendChild(div);lastDate=d}
    frag.appendChild(buildMsgEl(post,folder,q));
  }
  container.insertBefore(frag,container.firstChild);
  vState.offset=newOffset;
  container.scrollTop=container.scrollHeight-prevHeight+prevTop;
  if(newOffset>=total&&vState.scrollHandler)container.removeEventListener('scroll',vState.scrollHandler);
}

function buildMsgEl(post,folder,q){
  const isReply=!!post.root_id&&post.root_id!==post.id;
  const time=(post.created||'').slice(11,16);
  const div=document.createElement('div');
  div.className='msg'+(isReply?' reply':'');
  div.innerHTML=`<div class="avatar" style="${avatarStyle(post.username)}">${initials(post.username)}</div><div class="msg-body">${isReply?'<div class="reply-badge">↩ thread</div>':''}${!!post.pinned?'<div class="reply-badge" style="color:var(--yellow)">📌 pinned</div>':''}<div class="msg-header"><span class="msg-author">${esc(post.username)}</span><span class="msg-time">${time}</span></div><div class="msg-text">${formatText(post.message,q)}</div>${post.files?renderFiles(post.files,folder):''}</div>`;
  return div;
}

function debouncedRender(){clearTimeout(_searchTimer);_searchTimer=setTimeout(renderMessages,250)}

function renderFiles(files,folder){
  const imgs=files.filter(f=>isImage(f));const vids=files.filter(f=>isVideo(f));const others=files.filter(f=>!isImage(f)&&!isVideo(f));
  let html='';
  if(imgs.length){html+='<div class="msg-images">';for(const f of imgs){const src=state.images[f]||(folder?`${folder}/${encodeURIComponent(f)}`:null);if(src){html+=`<img class="msg-img" src="${src}" alt="${esc(f)}" title="${esc(f)}" onerror="this.outerHTML='<span class=\\'file-chip\\'>🖼 ${esc(f)}</span>'" onclick="openLightbox(this.src)">`}else{html+=`<span class="file-chip">🖼 ${esc(f)}</span>`}}html+='</div>'}
  if(vids.length){html+='<div class="msg-images">';for(const f of vids){const src=state.images[f]||(folder?`${folder}/${encodeURIComponent(f)}`:null);if(src){html+=`<video class="msg-video" src="${src}" title="${esc(f)}" controls preload="metadata" onerror="this.outerHTML='<span class=\\'file-chip\\'>🎬 ${esc(f)}</span>'"></video>`}else{html+=`<span class="file-chip">🎬 ${esc(f)}</span>`}}html+='</div>'}
  if(others.length){html+='<div class="msg-files">'+others.map(f=>`<span class="file-chip">📎 ${esc(f)}</span>`).join('')+'</div>'}
  return html;
}

function openLightbox(src){document.getElementById('lightbox-img').src=src;document.getElementById('lightbox').classList.add('open')}
function closeLightbox(){document.getElementById('lightbox').classList.remove('open')}

function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

function formatDate(iso){try{return new Date(iso).toLocaleDateString('pl-PL',{weekday:'long',year:'numeric',month:'long',day:'numeric'})}catch{return iso}}

function formatText(text,highlight){
  if(!text)return'<span style="color:var(--text3)">—</span>';
  const lines=text.split('\n');const outLines=[];let i=0;
  while(i<lines.length){
    const line=lines[i];
    if(line.trim().startsWith('|')&&i+1<lines.length&&/^\s*\|[\s\-:|]+\|\s*$/.test(lines[i+1])){
      const tableLines=[];
      while(i<lines.length&&lines[i].trim().startsWith('|')){tableLines.push(lines[i]);i++}
      const parseRow=(row)=>row.trim().replace(/^\||\|$/g,'').split('|').map(c=>c.trim());
      const headers=parseRow(tableLines[0]);const rows=tableLines.slice(2).map(parseRow);
      let table='<table class="msg-table"><thead><tr>';headers.forEach(h=>{table+=`<th>${esc(h)}</th>`});table+='</tr></thead><tbody>';
      rows.forEach(row=>{table+='<tr>';row.forEach(cell=>{table+=`<td>${esc(cell)}</td>`});table+='</tr>'});
      table+='</tbody></table>';outLines.push('\x00TABLE\x00'+table+'\x00/TABLE\x00');
    }else{outLines.push(lines[i]);i++}
  }
  const parts=outLines.join('\n').split(/\x00TABLE\x00([\s\S]*?)\x00\/TABLE\x00/);
  let html=parts.map((part,idx)=>idx%2===0?esc(part):part).join('');
  html=html.replace(/```([\s\S]*?)```/g,(_,code)=>`<pre><code>${code.trim()}</code></pre>`);
  html=html.replace(/`([^`]+)`/g,'<code>$1</code>');
  html=html.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  html=html.replace(/(https?:\/\/[^\s<>"]+)/g,'<a href="$1" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none">$1</a>');
  if(highlight){const re=new RegExp(`(${highlight.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')})`,'gi');html=html.replace(re,'<mark>$1</mark>')}
  return html;
}

const dropZone=document.getElementById('drop-zone');
const fileInput=document.getElementById('file-input');
const addFileInput=document.getElementById('add-file-input');
dropZone.addEventListener('dragover',e=>{e.preventDefault();dropZone.classList.add('over')});
dropZone.addEventListener('dragleave',()=>dropZone.classList.remove('over'));
dropZone.addEventListener('drop',e=>{e.preventDefault();dropZone.classList.remove('over');loadFiles(e.dataTransfer.files)});
fileInput.addEventListener('change',e=>loadFiles(e.target.files));
document.getElementById('add-more').addEventListener('click',()=>addFileInput.click());
addFileInput.addEventListener('change',e=>{loadFiles(e.target.files);addFileInput.value=''});
document.getElementById('ch-search').addEventListener('input',renderSidebar);
document.getElementById('msg-search').addEventListener('input',debouncedRender);
document.getElementById('filter-user').addEventListener('input',debouncedRender);
const folderInput=document.getElementById('folder-input');
document.getElementById('load-folder-btn').addEventListener('click',()=>folderInput.click());
folderInput.addEventListener('change',e=>{loadFiles(e.target.files);folderInput.value=''});
document.getElementById('messages').addEventListener('dragover',e=>e.preventDefault());
document.getElementById('messages').addEventListener('drop',e=>{e.preventDefault();loadFiles(e.dataTransfer.files)});
document.getElementById('clear-btn').addEventListener('click',()=>{if(confirm('Wyczyścić wszystkie zapisane kanały?'))clearStorage()});
document.getElementById('lightbox').addEventListener('click',closeLightbox);
document.getElementById('lightbox-close').addEventListener('click',closeLightbox);
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeLightbox();hideGlobalView()}});

async function globalSearch(){
  const q=document.getElementById('global-input').value.trim();
  if(q.length<2){showToast('Wpisz co najmniej 2 znaki');return}
  const btn=document.getElementById('global-btn');btn.disabled=true;btn.textContent='…';
  const resultsEl=document.getElementById('global-results');
  resultsEl.innerHTML='<div class="empty-state"><span>⏳</span>Szukam…</div>';
  showGlobalView();
  try{
    const resp=await fetch('/?search='+encodeURIComponent(q)+'&limit=100');
    const data=await resp.json();
    document.getElementById('gr-title').textContent='Wyniki: „'+data.query+'"';
    document.getElementById('gr-meta').textContent=data.count+' wyników'+(data.count>=100?' (pierwsze 100)':'');
    if(!data.results||!data.results.length){resultsEl.innerHTML='<div class="empty-state"><span>🔍</span>Brak wyników</div>'}
    else{
      resultsEl.innerHTML='';const frag=document.createDocumentFragment();
      for(const r of data.results){
        const div=document.createElement('div');div.className='gr-item';
        const snippet=r.message.length>300?r.message.slice(0,300)+'…':r.message;
        div.innerHTML='<div class="gr-channel">'+chIcon(r.channel_type)+' '+esc(r.channel_name)+'</div>'+'<div class="gr-meta">'+esc(r.username)+' · '+(r.created||'').slice(0,16).replace('T',' ')+'</div>'+'<div class="gr-text">'+highlightQuery(esc(snippet),q)+'</div>';
        div.onclick=()=>jumpToResult(r,q);frag.appendChild(div);
      }
      resultsEl.appendChild(frag);
      if(data.count>=100){const more=document.createElement('div');more.className='gr-more';more.textContent='Pokazano pierwsze 100 wyników.';resultsEl.appendChild(more)}
    }
  }catch(e){resultsEl.innerHTML='<div class="empty-state"><span>⚠️</span>Błąd wyszukiwania</div>';console.error(e)}
  btn.disabled=false;btn.textContent='Szukaj';
}

function highlightQuery(text,q){if(!q)return text;const re=new RegExp('('+q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','gi');return text.replace(re,'<mark>$1</mark>')}

async function jumpToResult(r,q){
  const idx=state.channels.findIndex(c=>c.jsonPath===r.channel_json);
  if(idx===-1){showToast('Kanał nie jest załadowany');return}
  hideGlobalView();await openChannel(idx);
  document.getElementById('msg-search').value=q;debouncedRender();
}

function showGlobalView(){document.getElementById('no-channel').style.display='none';document.getElementById('channel-view').style.display='none';document.getElementById('global-view').style.display='flex'}
function hideGlobalView(){document.getElementById('global-view').style.display='none';if(state.active!==null){document.getElementById('channel-view').style.display='flex'}else{document.getElementById('no-channel').style.display='flex'}}
document.getElementById('global-btn').addEventListener('click',globalSearch);
document.getElementById('global-input').addEventListener('keydown',e=>{if(e.key==='Enter')globalSearch()});
document.getElementById('gr-close').addEventListener('click',hideGlobalView);

function toggleTheme(){const isLight=document.documentElement.classList.toggle('light');document.getElementById('theme-toggle').textContent=isLight?'🌙 Dark':'☀ Light';localStorage.setItem('mm_theme',isLight?'light':'dark')}
if(localStorage.getItem('mm_theme')==='light'){document.documentElement.classList.add('light');document.addEventListener('DOMContentLoaded',()=>{const btn=document.getElementById('theme-toggle');if(btn)btn.textContent='🌙 Dark'})}

(function(){
  const resizer=document.getElementById('sidebar-resizer');const aside=resizer.parentElement;let startX,startW;
  resizer.addEventListener('mousedown',function(e){startX=e.clientX;startW=aside.offsetWidth;resizer.classList.add('dragging');document.body.style.cursor='col-resize';document.body.style.userSelect='none';
    function onMove(e){const w=Math.min(600,Math.max(160,startW+e.clientX-startX));aside.style.width=w+'px';document.documentElement.style.setProperty('--sidebar-w',w+'px')}
    function onUp(){resizer.classList.remove('dragging');document.body.style.cursor='';document.body.style.userSelect='';localStorage.setItem('mm_sidebar_w',aside.offsetWidth);document.removeEventListener('mousemove',onMove);document.removeEventListener('mouseup',onUp)}
    document.addEventListener('mousemove',onMove);document.addEventListener('mouseup',onUp);e.preventDefault()});
  const savedW=localStorage.getItem('mm_sidebar_w');if(savedW){aside.style.width=savedW+'px';document.documentElement.style.setProperty('--sidebar-w',savedW+'px')}
})();

async function init(){
  try{
    const resp=await fetch('/?api');
    if(resp.ok){const index=await resp.json();if(index.channels&&index.channels.length){await loadFromIndex(index);return}}
  }catch(e){console.log('[backup] brak serwera — fallback do localStorage',e)}
  if(loadFromStorage()){renderSidebar();showToast(`Przywrócono ${state.channels.length} kanał(ów) z pamięci`);return}
  document.getElementById('drop-screen').classList.add('visible');
}

async function loadFromIndex(index){
  state.channels=[];
  for(const entry of index.channels){
    state.channels.push({meta:{display_name:entry.display_name||entry.json.split('/').slice(-2)[0],type:entry.type||'?',id:entry.json,exported_at:entry.exported_at||'',team:''},posts:null,postCount:entry.post_count||0,jsonPath:entry.json,folder:entry.folder,images:entry.images||[]});
  }
  renderSidebar();showToast(`${index.channels.length} kanałów — kliknij aby otworzyć`);
}

async function ensurePostsLoaded(idx){
  const ch=state.channels[idx];if(ch.posts!==null)return;
  document.getElementById('tb-count').textContent='Ładuję…';
  try{
    const resp=await fetch(ch.jsonPath+'?v='+Date.now());if(!resp.ok)throw new Error(`HTTP ${resp.status}`);
    const data=await resp.json();const entry=Array.isArray(data)?data[0]:data;
    ch.posts=entry.posts||[];ch.meta={...entry.channel,id:entry.channel.id};ch.meta.display_name=entry.channel.display_name;
    renderSidebar();
  }catch(e){ch.posts=[];showToast(`Błąd ładowania: ${ch.jsonPath}`)}
}

init();
</script>
</body>
</html>"""


# ── API helpers ───────────────────────────────────────────────────────────────
def scan_for_json(base: Path):
    channels = []
    for path in sorted(base.rglob("*.json")):
        if path.name == "index.json":
            continue
        folder = path.parent
        display_name = folder.name
        ch_type = "?"
        post_count = 0
        exported_at = ""

        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
            entry = data[0] if isinstance(data, list) else data
            if entry.get("channel"):
                display_name = entry["channel"].get("display_name", display_name)
                ch_type      = entry["channel"].get("type", "?")
                exported_at  = entry["channel"].get("exported_at", "")
            if entry.get("posts"):
                post_count = len(entry["posts"])
        except Exception:
            pass

        media = sorted(
            f.name for f in folder.iterdir()
            if f.is_file() and f.suffix.lstrip(".").lower() in MEDIA_EXTS
        )

        rel_path   = "/" + path.relative_to(base.parent).as_posix()
        rel_folder = "/" + folder.relative_to(base.parent).as_posix()

        channels.append({
            "json":         rel_path,
            "folder":       rel_folder,
            "display_name": display_name,
            "type":         ch_type,
            "post_count":   post_count,
            "exported_at":  exported_at,
            "images":       media,
        })

    channels.sort(key=lambda c: c["display_name"])
    return channels


def search_in_json(base: Path, query: str, limit: int):
    results = []
    q_lower = query.lower()
    for path in sorted(base.rglob("*.json")):
        if path.name == "index.json":
            continue
        if len(results) >= limit:
            break
        try:
            content = path.read_text(encoding="utf-8")
            if q_lower not in content.lower():
                continue
            data = json.loads(content)
            entry = data[0] if isinstance(data, list) else data
            if not entry.get("posts"):
                continue

            ch_name = entry.get("channel", {}).get("display_name", path.parent.name)
            ch_type = entry.get("channel", {}).get("type", "?")
            rel_folder = "/" + path.parent.relative_to(base.parent).as_posix()
            rel_json   = "/" + path.relative_to(base.parent).as_posix()

            for post in entry["posts"]:
                if len(results) >= limit:
                    break
                msg = post.get("message", "")
                if not msg or q_lower not in msg.lower():
                    continue
                results.append({
                    "channel_name": ch_name,
                    "channel_type": ch_type,
                    "channel_json": rel_json,
                    "folder":       rel_folder,
                    "id":           post.get("id", ""),
                    "username":     post.get("username", ""),
                    "created":      post.get("created", ""),
                    "message":      msg,
                })
        except Exception:
            pass

    results.sort(key=lambda r: r["created"], reverse=True)
    return results


# ── HTTP handler ───────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path):
        MIME = {
            "html": "text/html; charset=utf-8",
            "json": "application/json; charset=utf-8",
            "png":  "image/png",
            "jpg":  "image/jpeg", "jpeg": "image/jpeg",
            "gif":  "image/gif",
            "webp": "image/webp",
            "svg":  "image/svg+xml",
            "mp4":  "video/mp4",
            "webm": "video/webm",
            "ogg":  "video/ogg",
            "mov":  "video/quicktime",
            "mkv":  "video/x-matroska",
        }
        ext  = path.suffix.lstrip(".").lower()
        mime = MIME.get(ext, "application/octet-stream")
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs     = urllib.parse.parse_qs(parsed.query)

        # ── ?api ──
        if "api" in qs or parsed.query == "api":
            if not RESULTS_DIR.is_dir():
                self.send_json(404, {"error": f"Folder '{RESULTS_DIR}' nie istnieje"})
                return
            channels = scan_for_json(RESULTS_DIR)
            self.send_json(200, {
                "generated_at": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "count":        len(channels),
                "channels":     channels,
            })
            return

        # ── ?search=… ──
        if "search" in qs:
            query = qs["search"][0].strip()
            limit = min(int(qs.get("limit", ["50"])[0]), SEARCH_LIMIT)
            if len(query) < 2:
                self.send_json(400, {"error": "Zapytanie musi mieć co najmniej 2 znaki", "results": []})
                return
            results = search_in_json(RESULTS_DIR, query, limit)
            self.send_json(200, {"query": query, "count": len(results), "results": results})
            return

        # ── static files inside results/ ──
        url_path = urllib.parse.unquote(parsed.path)
        results_url_prefix = "/" + RESULTS_DIR.name + "/"

        if url_path.startswith(results_url_prefix) or url_path.startswith("/" + RESULTS_DIR.name):
            # Strip leading /results_name
            relative = url_path[len("/" + RESULTS_DIR.name):].lstrip("/")
            file_path = RESULTS_DIR / relative
            # Prevent path traversal
            try:
                file_path.resolve().relative_to(RESULTS_DIR.resolve())
            except ValueError:
                self.send_response(403); self.end_headers(); return

            if file_path.is_file():
                self.send_file(file_path)
            else:
                self.send_response(404); self.end_headers()
            return

        # ── root → serve HTML viewer ──
        if url_path in ("/", "/index.php", "/index.html"):
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404); self.end_headers()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not RESULTS_DIR.exists():
        print(f"⚠  Folder '{RESULTS_DIR}' nie istnieje — zostanie użyty gdy się pojawi.")
    else:
        print(f"📁 results/: {RESULTS_DIR.resolve()}")

    server = HTTPServer(("", PORT), Handler)
    print(f"✅ Serwer działa → http://localhost:{PORT}")
    print("   Ctrl+C aby zatrzymać\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Zatrzymano.")
