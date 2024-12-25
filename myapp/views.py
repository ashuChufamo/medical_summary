from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import pandas as pd
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.tools.render import format_tool_to_openai_function
from langchain.schema.agent import AgentFinish
import os
from django.conf import settings
import re

# Use BASE_DIR to define relative paths
MEDICATION_LABS_FILE = os.path.join(settings.BASE_DIR, "Medication and Lab data Nov 2024.xlsx")
OPD_FILE = os.path.join(settings.BASE_DIR, "OPD data Nov 2024.xlsx")

medication_labs_data = pd.ExcelFile(MEDICATION_LABS_FILE)
opd_data = pd.ExcelFile(OPD_FILE)



def fetch_data_by_id(person_id):
    """Fetch data for the given person ID and map medicine IDs to names."""
    combined_data = []
    try:
        # Parse the medication list for mapping IDs to names
        medication_sheet_name = medication_labs_data.sheet_names[2]
        medication_df = medication_labs_data.parse(medication_sheet_name)
        medication_df.columns = medication_df.columns.str.strip()  # Clean column names
        medication_lookup = medication_df.set_index('IDlstmed')['lstmed_name'].to_dict()

        # Helper to standardize and find the ID column dynamically
        def find_and_match(df):
            normalized_columns = {col.strip().lower(): col for col in df.columns}
            id_col = normalized_columns.get('idpnt')
            if id_col:
                filtered_df = df[df[id_col].astype(str) == str(person_id)]
                if not filtered_df.empty:
                    return filtered_df.astype(str).to_dict(orient='records')
            return None

        # Parse OPD data and process medicine prescriptions
        for sheet in opd_data.sheet_names:
            df = opd_data.parse(sheet)
            matched_data = find_and_match(df)
            if matched_data:
                for record in matched_data:
                    if 'Medicine prescription' in record:
                        prescriptions = record['Medicine prescription']
                        record['Medicine prescription'] = parse_prescriptions(prescriptions, medication_lookup)
                    combined_data.append(record)

    except Exception as e:
        return {'error': str(e)}

    if not combined_data:
        return {'error': 'No data found for the given ID.'}
    return combined_data


def parse_prescriptions(prescriptions, medication_lookup):
    """Parse the Medicine prescription field and replace IDs with medication names."""
    try:
        # Extract ID mappings using regex
        matches = re.findall(r'ID"(\d+)"', prescriptions)
        if not matches:
            return prescriptions  # Return as-is if no IDs are found

        parsed_prescriptions = prescriptions
        for match in matches:
            med_name = medication_lookup.get(int(match), f"Unknown ID {match}")
            parsed_prescriptions = parsed_prescriptions.replace(f'ID"{match}"', f'{med_name}')

        return parsed_prescriptions
    except Exception as e:
        return f"Error parsing prescriptions: {e}"



def index(request):
    return render(request, 'index.html')

@csrf_exempt
def summarize(request):
    if request.method == 'POST':
        try:
            # Get the patient ID from the request
            data = json.loads(request.body.decode('utf-8'))
            person_id = data.get('person_id', None)

            if not person_id:
                return JsonResponse({'error': 'No person ID provided.'})

            # Fetch data for the person ID
            fetched_data = fetch_data_by_id(person_id)

            if 'error' in fetched_data:
                return JsonResponse({'error': fetched_data['error']})

            if not fetched_data:
                return JsonResponse({'error': 'No data found for the given ID.'})

            # Combine the data into a single string for the LLM
            medical_history = json.dumps(fetched_data, indent=2)

            # Summarization logic
            GOOGLE_API_KEY = "AIzaSyBFiAVIdjfpdK3UjqaZ-6QDq-xCSIS6XlA"  # Replace with your API key
            tools = []
            functions = [format_tool_to_openai_function(f) for f in tools]
            model = ChatGoogleGenerativeAI(
                model="gemini-1.5-pro-latest",
                google_api_key=GOOGLE_API_KEY,
                temperature=0.2,
            ).bind(functions=functions)

            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a helpful AI assistant specializing in summarizing medical histories. Provide a summary with clear and concise formatting. Use <strong>bold</strong> for important parts like examinations, tests, medications, complaints, and major recommendations. For critical or dangerous information like medical mismatches or high-risk conditions, use <span style='color:red;'>red</span> text to highlight them. You can also use <i>italics</i>, <ul> lists, <ol> lists, and <p> paragraphs. Keep the summary in one or two paragraphs."),
                ("user", "{input}"),
            ])

            chain = prompt | model | OpenAIFunctionsAgentOutputParser()

            # Formulate a question for the summarizer
            question = f"Summarize the following medical data: {medical_history}"

            response = chain.invoke({"input": question})

            if isinstance(response, AgentFinish):
                llm_response = response.return_values['output']
            else:
                llm_response = response

            # Clean up response text
            cleaned_response = llm_response.replace('*', '').replace('-', '').strip()

            return JsonResponse({'summary': cleaned_response})
        except Exception as e:
            return JsonResponse({'error': f'Error: {str(e)}'})

    return JsonResponse({'error': 'Invalid request method.'})
