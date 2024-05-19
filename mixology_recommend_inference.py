import os
import pickle

def make_recommendation(drink):
    with open ("data/mixology_sql.pkl", "rb") as f:
        data = pickle.load(f)
    target_index = list(data.keys()).index(drink)
    folder_path = "data/similarity_matrix"
    target_file = "%s/%s" % (folder_path, max([_ for _ in os.listdir(folder_path)], key=lambda f: os.path.getmtime(os.path.join(folder_path, f))))
    with open (target_file, "rb") as f:
        similarity_matrix = pickle.load(f)
    similar_drink_indices = similarity_matrix[target_index].argsort()[::-1]
    recommend_list, record_brand = [], set()
    for index in similar_drink_indices:
        if index == target_index:
            continue
        similar_drink = list(data.keys())[index]
        recommend_list.append(similar_drink)
    return recommend_list
