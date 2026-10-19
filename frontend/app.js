/* Frontend MVC: API centralizada, estado da navegação e views sem dependências externas. */
'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const brl = value => Number(value).toLocaleString('pt-BR', {style:'currency',currency:'BRL'});
const day = value => value ? value.slice(0,10).split('-').reverse().join('/') : '—';
const brazilDate = () => {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', {timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()).map(part=>[part.type,part.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
};
const plusDays = n => new Date(Date.parse(brazilDate()+'T00:00:00Z')+n*86400000).toISOString().slice(0,10);
const labels = {CONFIRMADA:'Confirmada',HOSPEDADA:'Hospedada',FINALIZADA:'Finalizada',CANCELADA:'Cancelada',MANUTENCAO:'Manutenção',LIVRE:'Livre',OCUPADO:'Ocupado',INATIVO:'Inativo',ESTORNADO:'Estornado',PAGO:'Pago'};
const badge = status => `<span class="badge ${esc(status)}">${esc(labels[status]||status)}</span>`;
const state = {user:null,page:'dashboard',offset:0,q:'',status:'',version:0};
let toastTimer;
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,6000);}
function signedOut(){state.user=null;$('#shell').hidden=true;$('#login-screen').hidden=false;$('#view').replaceChildren();$('#modal').close();$('#login-form input').focus();}
async function api(path, options={}){
  const headers = {'Content-Type':'application/json',...options.headers};
  if(state.user?.csrf) headers['X-CSRF-Token']=state.user.csrf;
  const response=await fetch('/api'+path,{...options,headers,credentials:'same-origin'});
  let data; try{data=await response.json();}catch{throw new Error('O servidor não respondeu corretamente. Tente novamente.');}
  if(!response.ok){
    if(response.status===401 && !path.includes('/auth/login')) signedOut();
    const fields=(data.campos||[]).map(item=>`${item.campo}: ${item.erro}`).join('\n');
    throw new Error((data.detail||'Não foi possível concluir a operação.')+(fields?'\n'+fields:''));
  }
  return data;
}
const send=(path,method,body)=>api(path,{method,body:body===undefined?undefined:JSON.stringify(body)});
function openModal(title,html){$('#modal-title').textContent=title;$('#modal-body').innerHTML=html;if(!$('#modal').open)$('#modal').showModal();const first=$('input,select,textarea,button',$('#modal-body'));if(first)first.focus();}
$('#close-modal').onclick=()=>$('#modal').close();
function field(name,label,value='',type='text',extra=''){return `<label>${esc(label)}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`;}
function select(name,label,options,value){return `<label>${esc(label)}<select name="${name}" aria-label="${esc(label)}" required>${options.map(([id,text])=>`<option value="${esc(id)}" ${String(id)===String(value)?'selected':''}>${esc(text)}</option>`).join('')}</select></label>`;}
function check(name,label,value){return `<label class="check"><input type="checkbox" name="${name}" ${value?'checked':''}>${esc(label)}</label>`;}
function textArea(name,label,value='',extra=''){return `<label class="full">${esc(label)}<textarea name="${name}" ${extra}>${esc(value)}</textarea></label>`;}
function formShell(html,label='Salvar'){return `<form id="editor"><div class="form-grid">${html}</div><p id="form-error" class="error" role="alert"></p><div class="form-actions"><button type="button" data-close>Voltar</button><button class="primary" type="submit">${label}</button></div></form>`;}
function bindForm(handler){
  $('[data-close]')?.addEventListener('click',()=>$('#modal').close());
  $('#editor').onsubmit=async event=>{event.preventDefault();const form=event.currentTarget, button=$('[type=submit]',form);button.disabled=true;$('#form-error').textContent='';try{await handler(form);$('#modal').close();await render();}catch(error){if($('#form-error'))$('#form-error').textContent=error.message;else toast(error.message);}finally{button.disabled=false;}};
}
const formData=form=>Object.fromEntries(new FormData(form));
const activeValue=(data,name='ativo')=>{data[name]=data[name]==='on';return data;};
function empty(message){return `<div class="empty">${esc(message)}</div>`;}
function table(headers,rows){return `<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;}
function pagination(total){return `<div class="pagination"><span>${total?state.offset+1:0}–${Math.min(state.offset+50,total)} de ${total}</span><button data-page="prev" ${state.offset===0?'disabled':''}>Anterior</button><button data-page="next" ${state.offset+50>=total?'disabled':''}>Próxima</button></div>`;}
function reservationRows(items){return items.map(r=>`<tr><td><strong>${esc(r.hospede_nome)}</strong><small>${esc(r.codigo)}</small></td><td>Quarto ${r.quarto_numero}<small>Prédio ${r.predio} · ${r.quantidade} pessoa(s)</small></td><td>${day(r.entrada)}<small>até ${day(r.saida)}</small></td><td>${badge(r.status)}</td><td>${brl(r.valor_total)}<small>Saldo ${brl(r.saldo)}</small></td><td><button data-detail="${r.id}">Ver reserva →</button></td></tr>`);}
function reserveTable(items){return items.length?table(['Hóspede / reserva','Quarto','Período','Situação','Valor',''],reservationRows(items)):empty('Nenhuma reserva neste período.');}
const titles={dashboard:['Visão geral','Seu dia na recepção, em um só lugar.'],reservas:['Reservas','Organize chegadas, estadias e partidas.'],hospedes:['Hóspedes','Cada estadia começa com um bom acolhimento.'],quartos:['Quartos e mapa','Acompanhe a ocupação e encontre o quarto ideal.'],historico:['Histórico','Consulte estadias anteriores e reservas canceladas.'],conta:['Minha conta','Mantenha o acesso da recepção protegido.']};
async function render(){
  if(!state.user)return;
  const version=++state.version;
  const [title,subtitle]=titles[state.page];$('#page-title').textContent=title;$('#page-subtitle').textContent=subtitle;
  document.querySelectorAll('nav a').forEach(a=>{const selected=a.hash==='#'+state.page;a.classList.toggle('active',selected);if(selected)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  $('#view').innerHTML='<div class="loading">Carregando informações…</div>';
  try{
    const html=await views[state.page]();
    if(version!==state.version||!state.user)return;
    $('#view').innerHTML=html;bindView();
  }catch(error){if(version===state.version&&state.user)$('#view').innerHTML=`<div class="panel empty"><p class="error">${esc(error.message)}</p><button id="retry">Tentar novamente</button></div>`;$('#retry')?.addEventListener('click',render);}
}
const views={
  async dashboard(){const d=await api('/dashboard');return `<section class="welcome"><div><h2>Uma boa recepção faz a diferença.</h2><p>${d.entradas.length} chegada(s) esperada(s) hoje. Tudo pronto para receber?</p></div><button class="primary" data-new="reservas">+ Nova reserva</button></section><div class="stats"><div class="stat"><span>Quartos ocupados</span><strong>${d.ocupados}<small>de ${d.quartos_ativos} quartos ativos</small></strong></div><div class="stat"><span>Chegadas de hoje</span><strong>${d.entradas.length}</strong><small>reservas confirmadas</small></div><div class="stat"><span>Hóspedes cadastrados</span><strong>${d.hospedes}</strong><small>cadastros ativos</small></div><div class="stat"><span>Recebimentos acumulados</span><strong>${brl(d.recebido)}</strong><small>descontados os estornos</small></div></div><section class="panel"><div class="panel-head"><div><h2>Chegadas de hoje</h2><p>Confirme a chegada e dê início à hospedagem.</p></div><a href="#reservas">Todas as reservas →</a></div>${reserveTable(d.entradas)}</section><section class="panel"><div class="panel-head"><div><h2>Saídas previstas e atrasadas</h2><p>O check-out libera o quarto para a próxima estadia.</p></div></div>${reserveTable(d.saidas)}</section>`;},
  async hospedes(){const d=await api(`/hospedes?q=${encodeURIComponent(state.q)}&offset=${state.offset}`);return `<form id="search" class="toolbar"><label class="grow">Buscar hóspede<input name="q" value="${esc(state.q)}" placeholder="Nome ou CPF" maxlength="150"></label><button>Buscar</button><button type="button" class="primary" data-new="hospedes">+ Novo hóspede</button></form><section class="panel">${d.items.length?table(['Hóspede','CPF','Contato','Situação',''],d.items.map(h=>`<tr><td><strong>${esc(h.nome)}</strong></td><td>${esc(h.cpf)}</td><td>${esc(h.email)}<small>${esc(h.telefone)}</small></td><td>${h.ativo?'Ativo':'Inativo'}</td><td><div class="actions"><button data-edit="hospedes" data-id="${h.id}">Editar</button><button data-delete="hospedes" data-id="${h.id}" class="danger">Excluir</button></div></td></tr>`)):empty('Nenhum hóspede encontrado. Cadastre o primeiro para criar reservas.')}${pagination(d.total)}</section>`;},
  async reservas(){return reservationList(false);},
  async historico(){return reservationList(true);},
  async quartos(){
    const items=await api('/quartos');
    const floors=[...new Set(items.map(r=>r.andar))].sort((a,b)=>a-b);
    const expected=[...Array(7)].map((_,i)=>101+i).concat([...Array(7)].map((_,i)=>201+i));
    const standardLayout=items.length===14&&items.every((r,i)=>r.predio===1&&r.numero===expected[i]&&r.andar===Math.floor(expected[i]/100));
    const floorMap=floors.map(floor=>{
      const rooms=items.filter(r=>r.andar===floor);
      const free=rooms.filter(r=>r.situacao_atual==='LIVRE').length;
      return `<section class="floor-section" aria-label="${floor}º andar"><div class="floor-head"><h2>${floor}º andar</h2><span>${free} livre(s) de ${rooms.length}</span></div><div class="room-grid">${rooms.map(r=>`<button class="room-card ${r.situacao_atual==='OCUPADO'?'occupied':''} ${['MANUTENCAO','INATIVO'].includes(r.situacao_atual)?'off':''}" data-edit="quartos" data-id="${r.id}"><small>${floor}º andar · até ${r.capacidade} pessoa(s)</small><strong>Quarto ${r.numero}</strong>${badge(r.situacao_atual)}<small>${brl(r.valor_diaria)}/noite</small></button>`).join('')}</div></section>`;
    }).join('');
    const layoutNote=standardLayout?'14 quartos fixos: 7 no 1º andar e 7 no 2º.':'Este banco já possuía outra planta de quartos; ela foi preservada para não alterar reservas anteriores. É necessária uma migração assistida para chegar aos 14 quartos.';
    const priceNote=standardLayout?`Diária: ${brl(100)} no 1º andar e ${brl(120)} no 2º.`:'As diárias preservadas deste banco aparecem em cada quarto.';
    return `<p class="help">${layoutNote} ${priceNote} Livre/Ocupado indica a situação agora; para datas futuras, consulte a disponibilidade. Clique em um quarto para alterar capacidade ou manutenção.</p><form id="availability" class="toolbar"><label>Entrada<input name="entrada" type="date" value="${plusDays(0)}" required></label><label>Saída<input name="saida" type="date" value="${plusDays(1)}" required></label><label>Pessoas<input name="pessoas" type="number" min="1" max="30" value="1" required></label><button>Consultar disponibilidade</button></form><div id="availability-result" aria-live="polite"></div>${floorMap}<section class="panel">${items.length?table(['Andar / quarto','Situação agora','Capacidade','Diária',''],items.map(r=>`<tr><td>${r.andar}º andar · Quarto ${r.numero}</td><td>${badge(r.situacao_atual)}</td><td>${r.capacidade} pessoas</td><td>${brl(r.valor_diaria)}</td><td><button data-edit="quartos" data-id="${r.id}">Editar</button></td></tr>`)):empty('Nenhum quarto cadastrado.')}</section>`;
  },
  async conta(){const rows=await api('/auditoria?limit=20');return `<section class="panel account"><h2>Alterar senha</h2><p class="help">Use ao menos 12 caracteres. A troca encerra todas as sessões desta conta.</p><form id="password-form">${field('senha_atual','Senha atual','','password','required autocomplete="current-password"')}${field('nova_senha','Nova senha','','password','required minlength="12" maxlength="200" autocomplete="new-password"')}<p class="error" role="alert" id="password-error"></p><button class="primary">Atualizar senha</button></form></section><section class="panel"><div class="panel-head"><h2>Atividade recente</h2></div>${rows.length?table(['Ação','Registro','Usuário','Data UTC'],rows.map(r=>`<tr><td>${esc(r.acao)}</td><td>${esc(r.entidade)} #${r.registro_id}</td><td>${esc(r.usuario)}</td><td>${esc(r.criado_em)}</td></tr>`)):empty('Nenhuma atividade registrada.')}</section>`;}
};
async function reservationList(history){
  const status=state.status||(history?'FINALIZADA':'');
  const d=await api(`/reservas?q=${encodeURIComponent(state.q)}&status=${encodeURIComponent(status)}&offset=${state.offset}`);
  const statuses=history?['FINALIZADA','CANCELADA']:['','CONFIRMADA','HOSPEDADA','FINALIZADA','CANCELADA'];
  return `<form id="search" class="toolbar"><label class="grow">Buscar reserva<input name="q" value="${esc(state.q)}" placeholder="Nome do hóspede ou código" maxlength="150"></label>${select('status','Situação',statuses.map(s=>[s,labels[s]||'Todas']),status)}<button>Filtrar</button>${history?'':'<button type="button" class="primary" data-new="reservas">+ Nova reserva</button>'}</form><section class="panel">${reserveTable(d.items)}${pagination(d.total)}</section>`;
}
function bindView(){
  $('#search')?.addEventListener('submit',event=>{event.preventDefault();const d=formData(event.currentTarget);state.q=d.q;state.status=d.status||'';state.offset=0;render();});
  document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>{state.offset+=b.dataset.page==='next'?50:-50;render();});
  document.querySelectorAll('[data-new]').forEach(b=>b.onclick=()=>safe(()=>edit(b.dataset.new)));
  document.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>safe(()=>edit(b.dataset.edit,Number(b.dataset.id))));
  document.querySelectorAll('[data-detail]').forEach(b=>b.onclick=()=>safe(()=>detail(Number(b.dataset.detail))));
  document.querySelectorAll('[data-delete]').forEach(b=>b.onclick=()=>safe(async()=>{if(!confirm('Excluir este registro? Se houver histórico, ele será desativado. Reservas ativas impedem a operação.'))return;const r=await send(`/${b.dataset.delete}/${b.dataset.id}`,'DELETE');toast(r.mensagem);await render();}));
  $('#availability')?.addEventListener('submit',event=>{event.preventDefault();safe(async()=>{const data=formData(event.currentTarget);const rows=await api('/quartos/disponiveis?'+new URLSearchParams(data));$('#availability-result').innerHTML=`<div class="quote">${rows.length?'<strong>Disponíveis neste período:</strong> '+rows.map(r=>`Prédio ${r.predio} / Quarto ${r.numero} (${brl(r.valor_diaria)}/noite)`).join(' · '):'Nenhum quarto disponível para este período e quantidade.'}</div>`;});});
  $('#password-form')?.addEventListener('submit',async event=>{event.preventDefault();const form=event.currentTarget,button=$('button',form);button.disabled=true;try{const result=await send('/auth/senha','PUT',formData(form));toast(result.mensagem);signedOut();}catch(error){$('#password-error').textContent=error.message;}finally{button.disabled=false;}});
}
async function safe(action){try{await action();}catch(error){toast(error.message);}}
async function edit(entity,id){
  const r=id?await api(`/${entity}/${id}`):{};
  if(entity==='hospedes'){
    const a=r.endereco||{};
    openModal(id?'Editar hóspede':'Novo hóspede',formShell(
      field('nome','Nome completo',r.nome,'text','required minlength="3" maxlength="150"')+field('cpf','CPF',r.cpf,'text','required maxlength="14" inputmode="numeric"')+
      field('nascimento','Data de nascimento',r.nascimento,'date','required')+field('email','E-mail',r.email,'email','required maxlength="200"')+
      field('telefone','Telefone',r.telefone,'tel','required minlength="8" maxlength="25"')+field('nacionalidade','Nacionalidade',r.nacionalidade||'Brasileira','text','required maxlength="60"')+
      field('genero','Gênero (opcional)',r.genero,'text','maxlength="40"')+check('ativo','Cadastro ativo',r.ativo??true)+
      '<p class="form-section full">Endereço individual</p>'+field('cep','CEP',a.cep,'text','required maxlength="9" inputmode="numeric"')+field('logradouro','Logradouro',a.logradouro,'text','required maxlength="150"')+
      field('numero','Número',a.numero,'text','required maxlength="20"')+field('complemento','Complemento',a.complemento,'text','maxlength="100"')+
      field('bairro','Bairro',a.bairro,'text','required maxlength="100"')+field('cidade','Cidade',a.cidade,'text','required maxlength="100"')+
      field('estado','Estado (UF)',a.estado,'text','required minlength="2" maxlength="2"')+field('pais','País',a.pais||'Brasil','text','required maxlength="60"')+textArea('observacoes','Observações',r.observacoes,'maxlength="1000"')));
    bindForm(async form=>{const d=activeValue(formData(form));d.endereco={};for(const k of ['cep','logradouro','numero','complemento','bairro','cidade','estado','pais']){d.endereco[k]=d[k];delete d[k];}await send('/hospedes'+(id?'/'+id:''),id?'PUT':'POST',d);toast('Hóspede salvo.');});
  }else if(entity==='quartos'){
    if(!id)throw new Error('Os quartos já estão cadastrados na planta fixa.');
    openModal('Editar quarto',formShell(field('predio','Prédio',r.predio,'number','required readonly')+field('numero','Número',r.numero,'number','required readonly')+
      field('andar','Andar',r.andar,'number','required readonly')+field('capacidade','Capacidade de pessoas',r.capacidade||2,'number','required min="1" max="30"')+
      select('status','Condição',[['DISPONIVEL','Disponível'],['MANUTENCAO','Em manutenção']],r.status||'DISPONIVEL')+check('ativo','Quarto ativo',r.ativo??true)+check('acessivel','Quarto acessível',r.acessivel)+textArea('descricao','Descrição',r.descricao,'maxlength="1000"')+
      `<p class="inline-help full">A planta e a diária são fixas: ${brl(r.valor_diaria)} por noite neste andar.</p>`));
    bindForm(async form=>{const d=activeValue(activeValue(formData(form)),'acessivel');for(const k of ['predio','numero','andar','capacidade'])d[k]=Number(d[k]);await send('/quartos/'+id,'PUT',d);toast('Quarto salvo.');});
  }else if(entity==='reservas'){
    const [guests,rooms]=await Promise.all([api('/hospedes?limit=50'),api('/quartos')]);
    let guestOptions=guests.items.filter(h=>h.ativo).map(h=>[h.id,h.nome+' · '+h.cpf]);
    if(id&&!guestOptions.some(([gid])=>gid===r.hospede_id))guestOptions.unshift([r.hospede_id,r.hospede_nome]);
    if(!guestOptions.length||!rooms.some(q=>q.ativo))throw new Error('Cadastre um hóspede ativo e um quarto antes de reservar.');
    openModal(id?'Editar reserva':'Nova reserva',formShell(
      '<label class="full">Localizar responsável<input id="guest-search" placeholder="Nome ou CPF (pesquisa entre todos os cadastros)" maxlength="150"></label><button type="button" id="find-guest" class="full">Buscar responsável</button>'+
      select('hospede_id','Responsável',guestOptions,r.hospede_id)+select('quarto_id','Quarto',rooms.filter(q=>q.ativo||q.id===r.quarto_id).map(q=>[q.id,`Prédio ${q.predio} · Quarto ${q.numero} · ${q.capacidade} pessoas · ${brl(q.valor_diaria)}/noite`]),r.quarto_id)+
      field('entrada','Entrada',r.entrada||plusDays(0),'date','required')+field('saida','Saída',r.saida||plusDays(1),'date','required')+
      textArea('nomes','Acompanhantes — um nome completo por linha',(r.acompanhantes||[]).map(a=>a.nome).join('\n'),'maxlength="4500"')+
      '<p class="inline-help full">O responsável já está incluído na contagem. Todos os nomes dos acompanhantes serão salvos.</p>'+
      field('desconto','Desconto (R$)',r.desconto||0,'number','required min="0" step="0.01"')+
      textArea('observacoes','Observações',r.observacoes,'maxlength="1000"')+
      '<div class="full"><button type="button" id="quote-button">Verificar disponibilidade e calcular</button><div id="quote-result" class="quote" aria-live="polite">O valor será calculado e validado pelo servidor.</div></div>',id?'Salvar alterações':'Confirmar reserva'));
    const payload=form=>{const d=formData(form);d.hospede_id=Number(d.hospede_id);d.quarto_id=Number(d.quarto_id);d.acompanhantes=d.nomes.split('\n').map(n=>n.trim()).filter(Boolean).map(nome=>({nome}));delete d.nomes;return d;};
    $('#find-guest').onclick=()=>safe(async()=>{const result=await api('/hospedes?limit=50&q='+encodeURIComponent($('#guest-search').value));const selectEl=$('[name=hospede_id]');selectEl.innerHTML=result.items.filter(h=>h.ativo).map(h=>`<option value="${h.id}">${esc(h.nome)} · ${esc(h.cpf)}</option>`).join('');if(!selectEl.options.length)toast('Nenhum hóspede ativo encontrado.');});
    $('#quote-button').onclick=()=>safe(async()=>{const quote=await send('/reservas/simular'+(id?'?reserva_id='+id:''),'POST',payload($('#editor')));$('#quote-result').textContent=`Disponível · ${quote.pessoas} pessoa(s) · ${quote.diarias} diária(s) de ${brl(quote.valor_diaria)} · Total ${brl(quote.total)}`;});
    $('#editor').addEventListener('input',()=>{$('#quote-result').textContent='Dados alterados. Verifique novamente o valor e a disponibilidade.';});
    bindForm(async form=>{await send('/reservas'+(id?'/'+id:''),id?'PUT':'POST',payload(form));toast('Reserva salva e disponibilidade confirmada.');});
  }
}
async function detail(id){
  const r=await api('/reservas/'+id);
  openModal(r.codigo,`<div>${badge(r.status)}</div><dl class="details"><div><dt>Responsável</dt><dd>${esc(r.hospede_nome)}</dd></div><div><dt>Acomodação</dt><dd>Prédio ${r.predio} · Quarto ${r.quarto_numero}</dd></div><div><dt>Entrada</dt><dd>${day(r.entrada)}</dd></div><div><dt>Saída prevista</dt><dd>${day(r.saida)}</dd></div><div><dt>Pessoas</dt><dd>${r.quantidade}</dd></div><div><dt>Diária contratada</dt><dd>${brl(r.valor_diaria)}</dd></div></dl><p class="help">Acompanhantes: ${(r.acompanhantes||[]).map(a=>esc(a.nome)).join(', ')||'Nenhum'}</p>${r.observacoes?`<p>${esc(r.observacoes)}</p>`:''}<div class="line"><span>Desconto</span><strong>${brl(r.desconto)}</strong></div><div class="line"><span>Total da estadia</span><strong>${brl(r.valor_total)}</strong></div><div class="line"><span>Saldo a receber</span><strong>${brl(r.saldo)}</strong></div><div class="form-actions">${r.status==='CONFIRMADA'?'<button id="edit-reservation">Editar</button><button class="danger" data-transition="cancelar">Cancelar reserva</button><button class="primary" data-transition="check-in">Fazer check-in</button>':''}${r.status==='HOSPEDADA'?'<button class="primary" data-transition="check-out">Fazer check-out</button>':''}</div><p class="form-section">Pagamentos registrados</p>${r.pagamentos.length?r.pagamentos.map(p=>`<div class="line"><span>${esc(p.forma)} · ${brl(p.valor)}<br>${badge(p.status)}</span>${p.status==='PAGO'?`<button data-refund="${p.id}">Registrar estorno</button>`:''}</div>`).join(''):'<p class="help">Ainda não há pagamentos.</p>'}${r.status!=='CANCELADA'&&r.saldo>0?'<div class="form-actions"><button id="new-payment">+ Registrar pagamento</button></div>':''}<p class="help">Os registros não movimentam dinheiro. Pagamentos e estornos devem ser realizados externamente.</p>`);
  $('#edit-reservation')?.addEventListener('click',()=>safe(()=>edit('reservas',id)));
  document.querySelectorAll('[data-transition]').forEach(b=>b.onclick=()=>safe(async()=>{if(!confirm(`Confirmar ${b.textContent.toLowerCase()}?`))return;b.disabled=true;try{await send(`/reservas/${id}/${b.dataset.transition}`,'PATCH');toast('Reserva atualizada.');await detail(id);await render();}finally{b.disabled=false;}}));
  $('#new-payment')?.addEventListener('click',()=>{openModal('Registrar pagamento',formShell(field('valor','Valor recebido (R$)',r.saldo,'number',`required min="0.01" max="${r.saldo}" step="0.01"`)+select('forma','Forma de pagamento',[['PIX','Pix'],['DINHEIRO','Dinheiro'],['CARTAO','Cartão'],['TRANSFERENCIA','Transferência']],'PIX')+'<p class="help full">Registre apenas um pagamento já recebido fora do sistema.</p>'));bindForm(async form=>{await send(`/reservas/${id}/pagamentos`,'POST',formData(form));toast('Pagamento registrado.');});});
  document.querySelectorAll('[data-refund]').forEach(b=>b.onclick=()=>{const paymentId=b.dataset.refund;openModal('Confirmar estorno realizado',formShell(textArea('motivo','Motivo do estorno','','required minlength="5" maxlength="300"')+check('confirmado','Confirmo que devolvi o valor externamente.',false)));$('[name=confirmado]').required=true;bindForm(async form=>{const d=formData(form);d.confirmado=d.confirmado==='on';await send(`/pagamentos/${paymentId}/estornar`,'POST',d);toast('Estorno registrado.');});});
}
$('#login-form').onsubmit=async event=>{event.preventDefault();const form=event.currentTarget,b=$('button',form);b.disabled=true;$('#login-error').textContent='';try{state.user=await send('/auth/login','POST',formData(form));form.reset();showApp();}catch(error){$('#login-error').textContent=error.message;}finally{b.disabled=false;}};
$('#logout').onclick=()=>safe(async()=>{await send('/auth/logout','POST');signedOut();});
function navigate(){state.page=location.hash.slice(1) in titles?location.hash.slice(1):'dashboard';state.offset=0;state.q='';state.status='';render();}
window.addEventListener('hashchange',navigate);
function showApp(){$('#login-screen').hidden=true;$('#shell').hidden=false;$('#user-name').textContent=state.user.nome;$('#today').textContent=new Intl.DateTimeFormat('pt-BR',{timeZone:'America/Sao_Paulo',day:'numeric',month:'long',year:'numeric'}).format(new Date());navigate();}
(async()=>{try{state.user=await api('/auth/me');showApp();}catch{signedOut();}})();
