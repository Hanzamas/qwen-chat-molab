dbg_cmd = mo.ui.text_area(value="nvidia-smi; ls ~/.humming/cache 2>/dev/null | tail -5", label="Shell (debug)", full_width=True)
dbg_btn = mo.ui.run_button(label="Run")
mo.accordion({"Debug shell": mo.vstack([dbg_cmd, dbg_btn])})
