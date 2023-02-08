import pandas as pd
from perseo.main import milisec
from template import Template
# from Hefesto.template import Template
import sys
import yaml
import math
import requests

class Hefesto():

    def __init__(self, datainput, reset = False):
        # Create an object as dictonary to reduce duplicate calls:
        self.reg = dict()

        # Import data input:
        if not reset:
            self.df_data = pd.read_csv(datainput)
        else:
            self.df_data = datainput
            return self.df_data

    def transform_Fiab(self):

    # Import static template for all CDE terms:
        temp = Template.template_model

    # Empty objects:
        resulting_df = pd.DataFrame()
        row_df = {}


        for row in self.df_data.iterrows():
            milisec_point = milisec()

            # Tag each row with the new of the model 
            new_row = {milisec_point : {"model": row[1]["model"]}}
            row_df.update(new_row)

            # Include columns related to ontological terms:
            for cde in temp.items():
                if cde[0] == row_df[milisec_point]["model"]:
                    row_df[milisec_point].update(cde[1])

            # Include columns from input CSV table:
            row_df[milisec_point].update(dict(row[1]))

            # Concate rows:
            final_row_df = pd.DataFrame(row_df[milisec_point], index=[1])
            resulting_df = pd.concat([resulting_df, final_row_df])
        # Reset Index:    
        resulting_df = resulting_df.reset_index(drop=True)
        # Turn any nan to None:
        resulting_df = resulting_df.where(pd.notnull(resulting_df), None)

        # Delete columns without values:
        for row_final in resulting_df.iterrows():
            if row_final[1]["value"] == None and row_final[1]["valueIRI"] == None:
                resulting_df = resulting_df.drop(row_final[0])

        # Datatype:
        datatype_relationship = {
            "xsd:string":"valueOutput_string",
            "xsd:date" : "valueOutput_date",
            "xsd:float": "valueOutput_float",
            "xsd:integer":"valueOutput_integer"
        }

        # Value edition:
        for index, row in resulting_df.iterrows():
            for k,v in datatype_relationship.items():

                # value ---> value_Output_DATATYPE:
                if row["value_datatype"] == k:
                    resulting_df.at[index, v] = resulting_df["value"][index]

                # valueIRI ---> processURI for Disability
                if row["model"] == "Disability" and row["valueIRI"] != None:
                    resulting_df.at[index, "processURI"] = resulting_df["valueIRI"][index]
                    resulting_df["valueIRI"][index] = None

                # enddate correction:
                if row["startdate"] != None and row["enddate"] == None:
                    resulting_df["enddate"][index] = resulting_df["startdate"][index]

        del resulting_df["value"]


        # valueIRI ---> valueAttributeIRI:
        del resulting_df["valueAttributeIRI"]
        resulting_df.rename(columns={'valueIRI':'valueAttributeIRI'}, inplace=True)

        # uniqid generation:
        resulting_df['uniqid'] = ""
        for i in resulting_df.index:
            resulting_df.at[i, "uniqid"] = milisec()

        print("Structural transformation: Done")
        new = Hefesto.__init__(self, datainput= resulting_df, reset = True)
        return new

    def transform_shape(self,configuration, uniqid_generation= True, contextid_generation= True, clean_blanks= False):

        if type(configuration) is not dict:
            sys.exit("configuration file must be a dictionary from a Python, YAML or JSON file")

        
        # Import static template for all CDE terms:
        temp = Template.template_model
        
        # Empty objects:
        resulting_df = pd.DataFrame()
        row_df = {}

        # Iterate each row from data input
        # check each YAML object from configuration file to set the parameters
        for row in self.df_data.iterrows():

            for config in configuration.items():

                # Create a unique stamp per new row to about them to colapse:
                milisec_point = milisec()

                row_df.update({milisec_point: {'model':config[1]["cde"]}})
                
                # Add YAML template static information
                for cde in temp.items():
                    if cde[0] == row_df[milisec_point]["model"]:
                        row_df[milisec_point].update(cde[1])

                # Relate each YAML parameter with original data input
                for element in config[1]["columns"].items():
                    for r in row[1].index:
                        if r == element[1]:
                            dict_element = {element[0]:row[1][r]}
                            row_df[milisec_point].update(dict_element)

                # Store formed element into the final table:
                final_row_df = pd.DataFrame(row_df[milisec_point], index=[1])
                resulting_df = pd.concat([resulting_df, final_row_df])

        # Reset Dataframe index
        resulting_df = resulting_df.reset_index(drop=True)

        if clean_blanks:
            # Replace all nan to None to easier removal
            resulting_df = resulting_df.where(pd.notnull(resulting_df), None)

            # Empty value row removal
            for row_final in resulting_df.iterrows():
                if row_final[1]["valueOutput_date"] == None and row_final[1]["valueOutput_string"] == None and row_final[1]["valueOutput_float"] == None:
                    resulting_df = resulting_df.drop(row_final[0])

            # Reset Dataframe index again
            resulting_df = resulting_df.reset_index(drop=True)
                    
        # uniqid (re)generation:
        resulting_df = resulting_df.reset_index(drop=True)

        if uniqid_generation:
            resulting_df['uniqid'] = ""
            for i in resulting_df.index:
                resulting_df.at[i, "uniqid"] = milisec()

        # context_id (re)generation:
        if contextid_generation:
            resulting_df['context_id'] = ""
            for i in resulting_df.index:
                resulting_df.at[i, "context_id"] = milisec()

        
        print("Structural transformation: Done")
        new = Hefesto.__init__(self, datainput= resulting_df, reset = True)
        return new

    def get_uri(self, col, ont):

        
        if not col in list(self.df_data.columns):
            sys.exit("ERROR: selected column doesnt exist")

        # Column duplication to work in new column:
        self.df_data[col+"_uri"] = self.df_data.loc[:, col]
        

        # Loop throught new column to replace current value with API term:
        for i in self.df_data[col+"_uri"].index:
            term = self.df_data.at[i,col+"_uri"]
            if term in self.reg:
                self.df_data.at[i,col+"_uri"] = self.reg[term] 

            else: # API call to OLS
                url= "http://www.ebi.ac.uk/ols/api/search?q="+ term +"&ontology=" + ont
                r = requests.get(url,headers= {"accept":"application/json"})
                data = r.json()
                # JSON navigation:
                try:
                    data_iri = data["response"]["docs"][0]["iri"]
                except IndexError:
                    data_iri = "NOT MATCH"
                # Attach new value to the Dataframe:
                self.reg[term] = data_iri
                self.df_data.at[i,col+"_uri"] = data_iri 

        print("URLs from Label calling: Done")
        new = Hefesto.__init__(self, datainput= self.df_data, reset = True)
        return new



    def get_label(self, col):

        # Column duplication to work in new column:
        self.df_data[col+"_label"] = self.df_data.loc[:, col]

        # Loop throught new column to replace current value with API term:
        for i in self.df_data[col+"_label"].index:
            term = self.df_data.at[i,col+"_label"]
            if term in self.reg:
                self.df_data.at[i,col+"_label"] = self.reg[term] 

            else: # API call to OLS
                url= 'http://www.ebi.ac.uk/ols/api/terms?iri='+ term
                r = requests.get(url,headers= {"accept":"application/json"}) # API call to OLS
                data = r.json()
                # JSON navigation:
                try:
                    data_label = data["_embedded"]["terms"][0]["label"]
                except TypeError:
                    data_label = "NOT MATCH"
                # Attach new value to the Dataframe:
                self.reg[term] = data_label
                self.df_data.at[i,col+"_label"] = data_label 

        print("Labels from URL calling: Done")
        new = Hefesto.__init__(self, datainput= self.df_data, reset = True)
        return new

    
    def replacement(self, col, key, value, duplicate = False):

        if duplicate == "True":
            # Column duplication to work in new column:
            self.df_data[col+"_dup"] = self.df_data.loc[:, col]
            self.df_data[col+"_dup"] = self.df_data[col+"_dup"].replace([key],value)
        else:
            self.df_data[col] = self.df_data[col].replace([key],value) 

        print("Replacement from " + key + "to "+ value + " at column " + col +": Done")
        new = Hefesto.__init__(self, datainput= self.df_data, reset = True)
        return new
        

# # Test 1:

test = Hefesto(datainput = "../data/input.csv")
transform = test.transform_Fiab()
transform.to_csv ("../data/CDEresult_final.csv", index = False, header=True)

# # Test 2
# with open("../data/CDEconfig.yaml") as file:
#     configuration = yaml.load(file, Loader=yaml.FullLoader)

# test = Hefesto(datainput = "../data/input2.csv")
# transform = test.transform_shape(configuration=configuration, clean_blanks = True) #, clean_blanks=False
# # label = test.get_label("outputURI")
# # url_from_label= test.get_uri("outputURI_label","ncit")
# # repl= test.replacement("outputURI_label", "Date","DateXXX", duplicate=False)
# transform.to_csv ("../data/result6.csv", index = False, header=True)