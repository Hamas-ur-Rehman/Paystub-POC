from services.assistant import Assitant
import gradio as gr

assistant = Assitant()

def process_form(state, zip_code, employee_status, full_name, ssn_last_4, dependent_total, other_income, deduction):
    # Here you would process the form data
    # For demo purposes, we'll just return a confirmation message
    pass
# Create the Gradio interface
with gr.Blocks() as demo:
    gr.Markdown("# Paystub DEMO")
    
    with gr.Row():
        with gr.Column(scale=6):
            gr.Markdown("## Company Information",container=False)
            with gr.Row():
                state = gr.Textbox(label="State *", placeholder="Enter state" ,container=False)
                zip_code = gr.Textbox(label="Zip Code (Optional)", placeholder="Enter zip code" ,container=False)
        
            gr.Markdown("## Employee Information" ,container=False)
            employee_status = gr.Radio(
                choices=["Employee", "Contractor"],
                label="Employee Status *",
                value="Employee",container=False
            )
            full_name = gr.Textbox(label="Employee Full Name *", placeholder="Enter full name",container=False)
            ssn_last_4 = gr.Textbox(
                label="Last 4 Digits of SSN *",
                placeholder="Enter last 4 digits",
                max_lines=1,container=False
            )
            
            with gr.Row():
                dependent_total = gr.Textbox(
                    label="Dependent Total (Optional)",
                    placeholder="Enter dependent total",container=False
                )
                other_income = gr.Textbox(
                    label="Other Income Amount (Optional)",
                    placeholder="Enter other income",container=False
                )
            
            deduction = gr.Textbox(
                label="Deduction Amount (Optional)",
                placeholder="Enter deduction amount",container=False
            )
            submit_btn = gr.Button("Submit")

        with gr.Column(scale=4):
            chatbot = gr.Chatbot(container=True)
            with gr.Row():    
                msg = gr.Textbox(scale=9,container=False)
                btn = gr.Button(value='submit', variant='primary',scale=3)

        def respond(message, history):
            if message == '':
                resp_message = "Please Enter a valid question"
                history = history + [[message,'']]
                history[-1][1] += resp_message
                yield "",history
            else:
                history = history + [[message,'']]
                for i in assistant.get_response(query=message,session_id='d386c061e082XSA'):
                    history[-1][1] += i
                    yield "",history
    
    msg.submit(respond, [msg, chatbot], [msg, chatbot])
    btn.click(respond, [msg, chatbot], [msg, chatbot])

    submit_btn.click(
        fn=process_form,
        inputs=[
            state,
            zip_code,
            employee_status,
            full_name,
            ssn_last_4,
            dependent_total,
            other_income,
            deduction
        ],
        outputs=None
    )

# Launch the interface
demo.launch(
    server_name="0.0.0.0",
    server_port=7860,
)