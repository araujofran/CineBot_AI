'use strict';
const el=id=>document.getElementById(id);
let busy=false, publicMode=false, ready=false, featured=[], catalogGeneration=0;
function safeURL(value, image=false){try{const u=new URL(value);if(!['https:','http:'].includes(u.protocol))return null;if(image&&u.hostname!=='static.tvmaze.com')return null;return u.href}catch{return null}}
function richText(target,text){
 const pattern=/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*\*([^*]+)\*\*/g;
 let last=0,match;
 for(const line of text.split('\n')){
  const row=document.createElement('div');last=0;pattern.lastIndex=0;
  while((match=pattern.exec(line))){row.append(document.createTextNode(line.slice(last,match.index)));if(match[3]){const strong=document.createElement('strong');strong.textContent=match[3];row.append(strong)}else{const url=safeURL(match[2]);if(url){const a=document.createElement('a');a.href=url;a.textContent=match[1];a.target='_blank';a.rel='noopener noreferrer';row.append(a)}else row.append(document.createTextNode(match[1]))}last=pattern.lastIndex}
  row.append(document.createTextNode(line.slice(last)||' '));target.append(row)
 }
}
function add(name,text,kind='assistant'){el('messages').querySelector('.welcome')?.remove();const box=document.createElement('div');box.className='message '+kind;const label=document.createElement('div');label.className='message-name';label.textContent=(kind==='assistant'?'✦ ':'')+name;box.append(label);const content=document.createElement('div');richText(content,text);box.append(content);el('messages').append(box);el('messages').scrollTop=el('messages').scrollHeight}
function state(value){busy=value;for(const id of ['send','forget','new-chat','user','token'])el(id).disabled=value;el('typing').hidden=!value}
async function request(path,method,body){const response=await fetch(path,{method,headers:{'Content-Type':'application/json','Authorization':'Bearer '+el('token').value.trim()},body:body?JSON.stringify(body):undefined});if(!response.ok){if([401,403].includes(response.status))throw Error('Digite a senha de acesso na lateral para começar.');if(response.status===429)throw Error('Vamos com calma: aguarde um minuto antes da próxima mensagem.');throw Error('Não conseguimos concluir agora. Tente novamente em instantes.')}return response.json()}
function choose(prompt){el('text').value=prompt;el('text').focus();if(innerWidth<1000)el('chat').scrollIntoView({behavior:'smooth',block:'start'})}
el('hero-chat').onclick=()=>choose('Me ajude a escolher uma boa história para assistir hoje. Faça uma pergunta para entender meu gosto.');
document.querySelectorAll('[data-prompt]').forEach(button=>button.onclick=()=>choose(button.dataset.prompt));
el('toggle-password').onclick=()=>{const visible=el('token').type==='password';el('token').type=visible?'text':'password';el('toggle-password').setAttribute('aria-label',visible?'Ocultar senha':'Mostrar senha')};
el('form').onsubmit=async event=>{event.preventDefault();if(busy||!ready)return;const text=el('text').value.trim(),user=el('user').value.trim();if(!text)return;if(!el('token').value.trim()){el('status').textContent='Primeiro, digite a senha de acesso.';el('token').focus();return}state(true);el('status').textContent='';add('Você',text,'user');try{const data=await request(publicMode?'/visit/chat':'/chat','POST',publicMode?{message:text}:{user_id:user,message:text});add('CineBot',data.answer);el('text').value=''}catch(error){el('status').textContent=error.message}finally{state(false);el('text').focus()}};
el('text').onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();el('form').requestSubmit()}};
async function forget(){if(busy||!ready)return;if(!el('token').value.trim()){el('status').textContent='Digite sua senha para apagar a memória.';el('token').focus();return}state(true);try{await request(publicMode?'/visit/memory':'/users/'+encodeURIComponent(el('user').value.trim())+'/memory','DELETE');el('messages').replaceChildren();add('CineBot','Uma nova sessão, uma nova história. O que vamos assistir hoje?');el('status').textContent=''}catch(error){el('status').textContent=error.message}finally{state(false)}}
el('forget').onclick=forget;el('new-chat').onclick=forget;
el('user').onchange=()=>{el('messages').replaceChildren();add('CineBot','Conversa selecionada. Me conte o que você está procurando.')};
const genreNames={'Science-Fiction':'Ficção científica','Thriller':'Suspense','Crime':'Crime','Drama':'Drama','Comedy':'Comédia','Adventure':'Aventura','Action':'Ação','Fantasy':'Fantasia','Horror':'Terror','Romance':'Romance','Mystery':'Mistério','History':'História','Family':'Família','Anime':'Anime','Music':'Música','War':'Guerra'};
function renderCards(shows){el('cards').replaceChildren();if(!shows.length){const empty=document.createElement('div');empty.className='empty-result';empty.textContent='Nenhuma série encontrada. Experimente o título original ou outra palavra.';el('cards').append(empty);return}
 for(const [index,show] of shows.entries()){
  const card=document.createElement('article');card.className='show-card';card.style.animationDelay=index*40+'ms';
  const poster=document.createElement('div');poster.className='poster-wrap';
  const url=safeURL(show.image,true);
  const fallback=()=>{const placeholder=document.createElement('div');placeholder.className='poster-placeholder';placeholder.textContent='✦';poster.prepend(placeholder)};
  if(url){const img=document.createElement('img');img.src=url;img.alt='Pôster de '+show.name;img.loading='lazy';img.width=210;img.height=315;img.onerror=()=>{img.remove();fallback()};poster.append(img)}else fallback();
  if(show.rating!=null){const rating=document.createElement('span');rating.className='rating';rating.textContent='★ '+show.rating;poster.append(rating)}
  const action=document.createElement('button');action.className='poster-action';action.textContent='Conversar sobre esta série ↗';action.onclick=()=>choose('Consulte o TVMaze e me conte sobre a série '+show.name+' (ID '+show.id+'). Ela combina com quem gosta de quê?');poster.append(action);
  const title=document.createElement('h3');title.textContent=show.name;title.title=show.name;
  const meta=document.createElement('div');meta.className='show-meta';meta.textContent=[show.premiered?.slice(0,4),...(show.genres||[]).slice(0,2).map(genre=>genreNames[genre]||genre)].filter(Boolean).join(' · ');
  card.append(poster,title,meta);
  const source=safeURL(show.url);if(source){const a=document.createElement('a');a.className='show-source';a.href=source;a.target='_blank';a.rel='noopener noreferrer';a.textContent='Ver no TVMaze ↗';card.append(a)}
  el('cards').append(card)
 }}
async function loadCatalog(query){const generation=++catalogGeneration;el('search-button').disabled=true;el('catalog-status').textContent=query?'Buscando no catálogo...':'Selecionando histórias...';try{let shows;if(!query&&featured.length){shows=featured}else{const r=await fetch(query?'/catalog/search?q='+encodeURIComponent(query):'/catalog/featured');if(!r.ok)throw Error('O catálogo está indisponível agora. Tente novamente.');shows=(await r.json()).results;if(!query)featured=shows}if(generation!==catalogGeneration)return;renderCards(shows);el('catalog-title').textContent=query?'Seu próximo resultado':'Histórias para conhecer';el('catalog-status').textContent=query?shows.length+' resultado(s) para “'+query+'”':'Uma seleção para abrir novos caminhos · séries';el('reset-search').hidden=!query}catch(error){if(generation!==catalogGeneration)return;el('cards').replaceChildren();el('catalog-status').textContent=error.message;el('reset-search').hidden=false}finally{if(generation===catalogGeneration)el('search-button').disabled=false}}
el('search-form').onsubmit=event=>{event.preventDefault();const q=el('search').value.trim();if(q.length>=2)loadCatalog(q)};
el('reset-search').onclick=()=>{el('search').value='';loadCatalog()};
fetch('/health').then(r=>{if(!r.ok)throw Error();return r.json()}).then(data=>{publicMode=data.public_mode;ready=true;el('user-label').hidden=publicMode;if(!publicMode)el('access-note').textContent='Informe o token da sua sessão local.';if(data.local_default_token)el('token').value='change-me';el('mode').lastChild.textContent=data.demo?' Modo demonstração':' IA conectada';if(data.demo){el('note').textContent='Modo demonstração: respostas da IA ainda não estão ativadas.'}else if(data.movie_catalog_enabled){el('note').textContent='Séries: TVMaze · Filmes e streaming: TMDB / JustWatch.'}loadCatalog()}).catch(()=>{el('mode').lastChild.textContent=' Offline';el('status').textContent='Não foi possível conectar. Atualize a página para tentar novamente.';el('catalog-status').textContent='Catálogo indisponível';el('cards').replaceChildren()});
