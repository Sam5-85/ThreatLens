(function(){
  const mount = document.getElementById("quiz-app");
  if(!mount) return;

  const quiz = JSON.parse(mount.dataset.quiz || "[]");
  const submitUrl = mount.dataset.submitUrl;
  const resultsUrl = mount.dataset.resultsUrl;

  const state = { index: 0, answers: {} };

  function el(tag, attrs={}, ...children){
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([k,v])=>{
      if(k === "class") node.className = v;
      else if(k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    });
    children.forEach(c=>{
      if(c == null) return;
      if(typeof c === "string") node.appendChild(document.createTextNode(c));
      else node.appendChild(c);
    });
    return node;
  }

  function render(){
    mount.innerHTML = "";

    const q = quiz[state.index];
    if(!q){
      mount.appendChild(el("p", {class:"muted"}, "No quiz questions loaded."));
      return;
    }

    const header = el("div", {class:"email-header"},
      el("div", {},
        el("h2", {}, `Question ${state.index+1} of ${quiz.length}`),
        el("div", {class:"muted"}, q.question)
      ),
      el("div", {class:"muted small"}, "Tip: Think about verification, urgency, and link safety.")
    );

    const form = el("div", {class:"card", style:"margin-top:12px; background: rgba(17,26,46,0.45);"},
      ...q.choices.map((choice, idx)=>{
        const id = `${q.id}-${idx}`;
        const checked = state.answers[q.id] === idx;
        return el("label", {for:id, style:"display:block; padding:10px; border-radius:12px; border:1px solid rgba(255,255,255,0.10); margin:8px 0; cursor:pointer;"},
          el("input", {
            type:"radio",
            name:q.id,
            id,
            value:String(idx),
            style:"margin-right:10px;",
            ...(checked ? {"checked":"checked"} : {}),
            onchange: () => { state.answers[q.id] = idx; }
          }),
          choice
        );
      })
    );

    const actions = el("div", {class:"actions"},
      el("button", {class:"btn ghost", type:"button", onclick: prev, ...(state.index===0 ? {"disabled":"disabled"} : {})}, "Back"),
      el("button", {class:"btn", type:"button", onclick: next}, state.index === quiz.length-1 ? "Submit" : "Next")
    );

    const wrap = el("div", {}, header, form, actions);
    mount.appendChild(wrap);
  }

  function prev(){
    state.index = Math.max(0, state.index - 1);
    render();
  }

  async function next(){
    if(state.index < quiz.length - 1){
      state.index += 1;
      render();
      return;
    }

    // Submit
    try{
      const payload = { answers: state.answers };
      const res = await fetch(submitUrl, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if(!data.ok) throw new Error(data.error || "Submit failed");
      window.location.href = resultsUrl;
    }catch(err){
      alert("Could not submit quiz: " + err.message);
    }
  }

  render();
})();
