import json
import os
import re
import shutil
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Tuple, Union

import cv2
import numpy as np
import pandas as pd
import skimage as ski
from colorama import Back, Fore, Style
from PIL import Image
from tomlkit.toml_document import TOMLDocument
from tqdm.auto import tqdm

from ....data.dataset.dsname import get_dsname_sortinfo
from ....dl.tester.utils import get_history_dir
from ....dl.utils import gen_class2num_dict
from ....shared.baseobject import BaseObject
from ....shared.config import load_config
from ....shared.utils import create_new_dir
from ...utils import (draw_predict_ans_on_image, draw_x_on_image, get_font,
                      plot_with_imglist_auto_row)
from .utils import get_gallery_column
# -----------------------------------------------------------------------------/


class CamGalleryCreator(BaseObject):

    def __init__(self, display_on_CLI=True) -> None:
        """
        """
        # ---------------------------------------------------------------------
        # """ components """
        
        super().__init__(display_on_CLI)
        self._cli_out._set_logger("Cam Gallery Creator")
        
        # ---------------------------------------------------------------------
        # """ attributes """
        # TODO
        # ---------------------------------------------------------------------
        # """ actions """
        # TODO
        # ---------------------------------------------------------------------/


    def _set_attrs(self, config:Union[str, Path]):
        """
        """
        super()._set_attrs(config)
        self._set_history_dir()
        self._set_training_config_attrs()
        self._set_config_attrs_default_value()
        
        self._set_src_root()
        self._set_test_df()
        self._set_mapping_attrs()
        self._set_predict_ans_dict()
        self._set_cam_result_root()
        
        self._set_cam_gallery_dir()
        self._set_rank_dict()
        # ---------------------------------------------------------------------/


    def _set_config_attrs(self):
        """
        """
        """ [model_prediction] """
        self.model_time_stamp: str = self.config["model_prediction"]["time_stamp"]
        self.model_state: str = self.config["model_prediction"]["state"]
        
        """ [layout] """
        self.column: int = self.config["layout"]["column"]
        
        """ [draw.drop_image.line] """
        self.line_color: list = self.config["draw"]["drop_image"]["line"]["color"]
        self.line_width: int = self.config["draw"]["drop_image"]["line"]["width"]
        
        """ [draw.cam_image] """
        self.cam_weight: float = self.config["draw"]["cam_image"]["weight"]
        
        """ [draw.cam_image.replace_color] """
        self.replace_cam_color: bool = self.config["draw"]["cam_image"]["replace_color"]["enable"]
        self.replaced_colormap: int = getattr(cv2, self.config["draw"]["cam_image"]["replace_color"]["colormap"])
        
        """ [draw.cam_image.text] """
        self.text_font_style: Union[str, list] = self.config["draw"]["cam_image"]["text"]["font_style"]
        self.text_font_size: Union[int, list] = self.config["draw"]["cam_image"]["text"]["font_size"]
        
        """ [draw.cam_image.text.color] """
        self.text_correct_color: list = self.config["draw"]["cam_image"]["text"]["color"]["correct"]
        self.text_incorrect_color: list = self.config["draw"]["cam_image"]["text"]["color"]["incorrect"]
        self.text_shadow_color: list = self.config["draw"]["cam_image"]["text"]["color"]["shadow"]
        # ---------------------------------------------------------------------/


    def _set_history_dir(self):
        """
        """
        self.history_dir = get_history_dir(self._path_navigator,
                                           self.model_time_stamp,
                                           self.model_state,
                                           cli_out=self._cli_out)
        # ---------------------------------------------------------------------/


    def _set_training_config_attrs(self):
        """
        """
        path = self.history_dir.joinpath("training_config.toml")
        if not path.exists():
            raise FileNotFoundError(f"{Fore.RED}{Back.BLACK} "
                                    f"Can't find 'training_config.toml' "
                                    f"( loss the most important file ). "
                                    f"{Style.RESET_ALL}\n")
        
        self.training_config: Union[dict, TOMLDocument] = \
                                load_config(path, cli_out=self._cli_out)
        
        """ [dataset] """
        self.dataset_seed_dir: str = self.training_config["dataset"]["seed_dir"]
        self.dataset_data: str = self.training_config["dataset"]["data"]
        self.dataset_palmskin_result: str = self.training_config["dataset"]["palmskin_result"]
        self.dataset_base_size: str = self.training_config["dataset"]["base_size"]
        self.dataset_classif_strategy: str = self.training_config["dataset"]["classif_strategy"]
        self.dataset_file_name: str = self.training_config["dataset"]["file_name"]
        
        """ [train_opts.data] """
        self.add_bg_class: bool = self.training_config["train_opts"]["data"]["add_bg_class"]
        # ---------------------------------------------------------------------/


    def _set_config_attrs_default_value(self):
        """
        """
        """ [layout] """
        if not self.column:
            self.column = get_gallery_column(self.dataset_base_size,
                                                self.dataset_file_name)
        
        """ [draw.drop_image.line] """
        if not self.line_color: self.line_color = (180, 160, 0)
        if not self.line_width: self.line_width = 2
        
        """ [draw.cam_image] """
        if not self.cam_weight: self.cam_weight = 0.5
        
        """ [draw.cam_image.text] """
        if not self.text_font_style: self.text_font_style = \
                            str(get_font(alt_default_family="monospace"))
        if not self.text_font_size: self.text_font_size = None
        
        """ [draw.cam_image.text.color] """
        if not self.text_correct_color: self.text_correct_color = (0, 255, 0)
        if not self.text_incorrect_color: self.text_incorrect_color = (255, 255, 255)
        if not self.text_shadow_color: self.text_shadow_color = (0, 0, 0)
        # ---------------------------------------------------------------------/


    def _set_src_root(self):
        """
        """
        dataset_cropped: Path = \
            self._path_navigator.dbpp.get_one_of_dbpp_roots("dataset_cropped_v3")
        
        self.src_root = dataset_cropped.joinpath(self.dataset_seed_dir,
                                                 self.dataset_data,
                                                 self.dataset_palmskin_result,
                                                 self.dataset_base_size)
        # ---------------------------------------------------------------------/


    def _set_test_df(self):
        """
        """
        dataset_file: Path = self.src_root.joinpath(self.dataset_classif_strategy,
                                                    self.dataset_file_name)
        
        if not dataset_file.exists():
            raise FileNotFoundError(f"{Fore.RED}{Back.BLACK} "
                                    f"Can't find target dataset file "
                                    f"run `1.2.create_dataset_file.py` to create it. "
                                    f"{Style.RESET_ALL}\n")
        
        dataset_df: pd.DataFrame = \
            pd.read_csv(dataset_file, encoding='utf_8_sig')
        
        self.test_df: pd.DataFrame = \
            dataset_df[(dataset_df["dataset"] == "test")]
        # ---------------------------------------------------------------------/


    def _set_mapping_attrs(self):
        """ Set below attributes
            >>> self.num2class_list: list
            >>> self.class2num_dict: dict[str, int]
        
        Example :
        >>> num2class_list = ['L', 'M', 'S']
        >>> class2num_dict = {'L': 0, 'M': 1, 'S': 2}
        """
        cls_list = list(Counter(self.test_df["class"]).keys())
        
        if self.add_bg_class:
            cls_list.append("BG")
        
        self.num2class_list: list = sorted(cls_list)
        self.class2num_dict: dict[str, int] = gen_class2num_dict(self.num2class_list)
        
        self._cli_out.write(f"num2class_list = {self.num2class_list}, "
                            f"class2num_dict = {self.class2num_dict}")
        # ---------------------------------------------------------------------/


    def _set_predict_ans_dict(self):
        """
        """
        log_path = self.history_dir.joinpath(r"{Logs}_PredByFish_predict_ans.log")
        if not log_path.exists():
            raise FileNotFoundError(f"{Fore.RED}{Back.BLACK} Can't find file: "
                                    r"'{Logs}_PredByFish_predict_ans.log' "
                                    f"run `3.2.{{TestByFish}}_vit_b_16.py` to create it"
                                    f"{Style.RESET_ALL}\n")
        
        with open(log_path, 'r') as f_reader: 
            self.predict_ans_dict = json.load(f_reader)
        # ---------------------------------------------------------------------/


    def _set_cam_result_root(self):
        """
        """
        self.cam_result_root: Path = self.history_dir.joinpath("cam_result")
        if not self.cam_result_root.exists():
            raise FileNotFoundError(f"{Fore.RED}{Back.BLACK} "
                                    f"Can't find directory: 'cam_result/' "
                                    f"run `3.2.{{TestByFish}}_vit_b_16.py` and "
                                    f"set (config) `cam.enable` = true. "
                                    f"{Style.RESET_ALL}\n")
        # ---------------------------------------------------------------------/


    def _set_cam_gallery_dir(self):
        """
        """
        self.cam_gallery_dir = self.history_dir.joinpath("+---CAM_Gallery")
        if self.cam_gallery_dir.exists():
            raise FileExistsError(f"{Fore.RED}{Back.BLACK} "
                                  f"Directory already exists: '{self.cam_gallery_dir}'. "
                                  f"To re-generate, please delete it manually. "
                                  f"{Style.RESET_ALL}\n")
        # ---------------------------------------------------------------------/


    def _set_rank_dict(self):
        """
        """
        self.rank_dict: dict = {}
        
        for i in range(10+1):
            if i < 5: self.rank_dict[i*10] = f"Match{str(i*10)}_(misMatch)"
            elif i == 10: self.rank_dict[i*10] = f"Match{str(i*10)}_(Full)"
            else: self.rank_dict[i*10] =  f"Match{str(i*10)}"
        # ---------------------------------------------------------------------/


    def run(self, config:Union[str, Path]):
        """

        Args:
            config (Union[str, Path]): a toml file.
        """
        super().run(config)
        
        # self._create_rank_dirs()
        
        fish_dsnames = sorted(Counter(self.test_df["parent (dsname)"]).keys(),
                              key=get_dsname_sortinfo)
        # fish_dsnames = fish_dsnames[:5] # for debug
        
        self._cli_out.divide()
        self._progressbar = tqdm(total=len(fish_dsnames), desc=f"[ {self._cli_out.logger_name} ] : ")
        
        for fish_dsname in fish_dsnames:
            self._progressbar.desc = f"[ {self._cli_out.logger_name} ] Generating '{fish_dsname}' "
            self._progressbar.refresh()
            self.gen_single_cam_gallery(fish_dsname)
        
        self._progressbar.close()
        # self._del_empty_rank_dirs()
        self._cli_out.new_line()
        # ---------------------------------------------------------------------/


    def _create_rank_dirs(self): # deprecated
        """ (deprecated)
        """
        for key in self.num2class_list:
            for _, value in self.rank_dict.items():
                create_new_dir(self.cam_gallery_dir.joinpath(key, value))
        # ---------------------------------------------------------------------/


    def gen_single_cam_gallery(self, fish_dsname:str):
        """
        """
        fish_cls = self._get_fish_cls(fish_dsname)
        
        tested_paths, \
            untest_paths, \
                cam_result_paths = self._get_path_lists(fish_dsname)
        
        self._read_images_as_dict(tested_paths, # --> self.tested_img_dict
                                  untest_paths,  # --> self.untest_img_dict
                                  cam_result_paths)  # --> self.cam_result_img_dict
        
        # >>> draw on 'untest' images <<<
        for untest_name, untest_img in self.untest_img_dict.items():
            self._draw_on_drop_image(untest_name, untest_img)
        
        # >>> draw on `cam` images <<<
        self.correct_cnt: int = 0 # reset value
        for (cam_name, cam_img), (tested_name, tested_img) \
            in zip(self.cam_result_img_dict.items(), self.tested_img_dict.items()):
                self._draw_on_cam_image(cam_name, cam_img,
                                        tested_name, tested_img,
                                        fish_cls)
        
        # >>> check which `rank_dir` to store <<<
        # self._calculate_correct_rank()
        
        # >>> orig: `tested_img_dict` + `untest_img_dict` <<<
        self._gen_orig_gallery(fish_dsname, fish_cls)
        
        # >>> overlay: `cam_result_img_dict` + `untest_img_dict` <<<
        self._gen_overlay_gallery(fish_dsname, fish_cls)
        
        # >>> update pbar <<<
        self._progressbar.update(1)
        self._progressbar.refresh()
        # ---------------------------------------------------------------------/


    def _get_fish_cls(self, fish_dsname:str) -> str:
        """
        """
        df = self.test_df[(self.test_df["parent (dsname)"] == fish_dsname)]
        
        # get voted class
        class_cnt: Counter = Counter()
        for crop_name in df["image_name"]:
            try:
                # if image is tested
                class_cnt.update([self.predict_ans_dict[crop_name]["gt"]])
            except KeyError:
                pass
        
        return class_cnt.most_common(1)[0][0]
        # ---------------------------------------------------------------------/


    def _get_path_lists(self, fish_dsname:str)-> tuple[list, list, list]:
        """
        """   
        # >>> cam result (tested) <<<
        
        cam_result_paths: list[Path] = []
        if self.replace_cam_color:
            cam_result_paths = sorted(self.cam_result_root.glob(f"{fish_dsname}/grayscale_map/*.tiff"),
                                          key=get_dsname_sortinfo)
        else:
            cam_result_paths = sorted(self.cam_result_root.glob(f"{fish_dsname}/color_map/*.tiff"),
                                          key=get_dsname_sortinfo)
        cam_dict: dict[int, Path] = \
            {get_dsname_sortinfo(path)[-1]: path for path in cam_result_paths}
        
        # >>> test_df <<<
        
        df = self.test_df[(self.test_df["parent (dsname)"] == fish_dsname)]
        tmp_dict: dict[int, Path] = \
            {get_dsname_sortinfo(path)[-1]: \
                self.src_root.joinpath(path) for path in df["path"]}
        
        # >>> Seperate 'tested' / 'untest' (without CAM) <<<
        
        # tested (predict)
        tested_paths: list[Path] = []
        for crop_sn in cam_dict.keys():
            tested_paths.append(tmp_dict.pop(crop_sn))
        
        # untest (not predict)
        untest_paths: list[Path] = list(tmp_dict.values())
        
        # >>> return <<<
        return tested_paths, untest_paths, cam_result_paths
        # ---------------------------------------------------------------------/


    def _read_images_as_dict(self, tested_paths:list,
                                   untest_paths:list,
                                   cam_result_paths:list):
        """
        """
        # self.tested_img_dict: dict[str, np.ndarray] = \
        #     { os.path.split(os.path.splitext(path)[0])[-1]: \
        #         cv2.imread(str(path)) for path in tested_paths }
        self.tested_img_dict: dict[str, np.ndarray] = \
            { path.stem: ski.io.imread(path) for path in tested_paths }
        
        # self.untest_img_dict: dict[str, np.ndarray] = \
        #     { os.path.split(os.path.splitext(path)[0])[-1]: \
        #         cv2.imread(str(path)) for path in untest_paths }
        self.untest_img_dict: dict[str, np.ndarray] = \
            { path.stem: ski.io.imread(path) for path in untest_paths }
        
        # self.cam_result_img_dict: dict[str, np.ndarray] = \
        #     { os.path.split(os.path.splitext(path)[0])[-1]: \
        #         cv2.imread(str(path)) for path in cam_result_paths }
        self.cam_result_img_dict: dict[str, np.ndarray] = \
            { path.stem: ski.io.imread(path) for path in cam_result_paths }
        # ---------------------------------------------------------------------/


    def _draw_on_drop_image(self, untest_name:str, untest_img:np.ndarray):
        """
        """
        assert untest_img.dtype == np.uint8, "untest_img.dtype != np.uint8"
        
        rgb_img = Image.fromarray(np.uint8(untest_img*0.5)) # convert to pillow image before drawing
        draw_x_on_image(rgb_img, self.line_color, self.line_width)
        
        # >>> replace image <<<
        assert id(untest_img) != id(rgb_img)
        self.untest_img_dict[untest_name] = np.array(rgb_img)
        # ---------------------------------------------------------------------/


    def _draw_on_cam_image(self, cam_name:str, cam_img:np.ndarray,
                                 tested_name:str, tested_img:np.ndarray,
                                 fish_cls:str):
        """
        """
        assert get_dsname_sortinfo(cam_name) == get_dsname_sortinfo(tested_name)
        assert cam_img.dtype == np.uint8, "cam_img.dtype != np.uint8"
        assert tested_img.dtype == np.uint8, "tested_img.dtype != np.uint8"
        
        # preparing `cam_rgb_img` (np.float64)
        if self.replace_cam_color:
            cam_bgr_img = cv2.applyColorMap(cam_img, self.replaced_colormap) # BGR
            cam_rgb_img = cv2.cvtColor(cam_bgr_img, cv2.COLOR_BGR2RGB)/255.0
        else:
            cam_rgb_img = cam_img/255.0
        
        # preparing `tested_rgb_img` (np.float64)
        tested_rgb_img = tested_img/255.0
        
        # overlay `cam_img` on `tested_img`
        cam_overlay = (cam_rgb_img*self.cam_weight + 
                       tested_rgb_img*(1 - self.cam_weight))
        
        # get 'sub-crop' predicted results for `draw_predict_ans_on_image`
        gt_cls = self.predict_ans_dict[tested_name]['gt']
        pred_cls = self.predict_ans_dict[tested_name]['pred']
        
        if pred_cls != gt_cls:
            # create a red mask
            mask = np.zeros_like(cam_overlay, dtype=np.float64) # black mask
            mask[:, :, 0] = 1.0 # modify to `red` mask
            # fusion with red mask
            mask_overlay = cam_overlay*0.7 + mask*0.3
            mask_overlay = np.uint8(mask_overlay*255)
            # draw text
            rgb_img = Image.fromarray(mask_overlay) # convert to pillow image before drawing
            draw_predict_ans_on_image(rgb_img, pred_cls, gt_cls,
                                      self.text_font_style, self.text_font_size,
                                      self.text_correct_color,
                                      self.text_incorrect_color,
                                      self.text_shadow_color)
            cam_overlay = np.array(rgb_img)
        else:
            self.correct_cnt += 1
            cam_overlay = np.uint8(cam_overlay*255)
            # for `add_bg_class` flag
            if fish_cls != gt_cls:
                rgb_img = Image.fromarray(cam_overlay) # convert to pillow image before drawing
                draw_predict_ans_on_image(rgb_img, pred_cls, gt_cls,
                                          self.text_font_style, self.text_font_size,
                                          self.text_correct_color,
                                          self.text_incorrect_color,
                                          self.text_shadow_color)
                cam_overlay = np.array(rgb_img)
        
        # >>> replace image <<<
        assert id(cam_img) != id(cam_overlay)
        self.cam_result_img_dict[cam_name] = cam_overlay
        # ---------------------------------------------------------------------/


    def _calculate_correct_rank(self): # deprecated
        """ (deprecated)
        """
        self.matching_ratio_percent = int((self.correct_cnt / len(self.cam_result_img_dict))*100)
        for key, value in self.rank_dict.items():
            if self.matching_ratio_percent >= key: self.cls_matching_state = value
        # ---------------------------------------------------------------------/


    def _gen_orig_gallery(self, fish_dsname:str, fish_cls:str):
        """
        """
        img_dict: dict = deepcopy(self.tested_img_dict)
        img_dict.update(self.untest_img_dict)
        sorted_img_dict = OrderedDict(sorted(list(img_dict.items()), key=lambda x: get_dsname_sortinfo(x[0])))
        img_list = [ img for _, img in sorted_img_dict.items() ]
        
        # score
        accuracy = self.correct_cnt / len(self.cam_result_img_dict)
        
        # >>> plot with 'Auto Row Calculation' <<<
        figtitle = (f"( original ) [{fish_cls}] {fish_dsname} : "
                    f"{self.dataset_palmskin_result}, "
                    f"{os.path.splitext(self.dataset_file_name)[0]}")
        save_path = self.cam_gallery_dir.joinpath(f"{fish_cls}/{accuracy:0.5f}_{fish_dsname}_orig.png")
        create_new_dir(save_path.parent)
        
        kwargs_plot_with_imglist_auto_row = {
            "img_list"   : img_list,
            "column"     : self.column,
            "fig_dpi"    : 200,
            "figtitle"   : figtitle,
            "save_path"  : save_path,
            "use_rgb"    : True,
            "show_fig"   : False
        }
        plot_with_imglist_auto_row(**kwargs_plot_with_imglist_auto_row)
        # ---------------------------------------------------------------------/


    def _gen_overlay_gallery(self, fish_dsname:str, fish_cls:str):
        """
        """
        img_dict: dict = deepcopy(self.cam_result_img_dict)
        img_dict.update(self.untest_img_dict)
        sorted_img_dict = OrderedDict(sorted(list(img_dict.items()), key=lambda x: get_dsname_sortinfo(x[0])))
        img_list = [ img for _, img in sorted_img_dict.items() ]
        
        # score
        accuracy = self.correct_cnt / len(self.cam_result_img_dict)
        
        # >>> plot with 'Auto Row Calculation' <<<
        figtitle = (f"( cam overlay ) [{fish_cls}] {fish_dsname} : "
                    f"{self.dataset_palmskin_result}, "
                    f"{os.path.splitext(self.dataset_file_name)[0]}, "
                    f"correct : {self.correct_cnt}/{len(self.cam_result_img_dict)} ({accuracy:.2f})")
        save_path = self.cam_gallery_dir.joinpath(f"{fish_cls}/{accuracy:0.5f}_{fish_dsname}_overlay.png")
        create_new_dir(save_path.parent)
        
        kwargs_plot_with_imglist_auto_row = {
            "img_list"   : img_list,
            "column"     : self.column,
            "fig_dpi"    : 200,
            "figtitle"   : figtitle,
            "save_path"  : save_path,
            "use_rgb"    : True,
            "show_fig"   : False
        }
        plot_with_imglist_auto_row(**kwargs_plot_with_imglist_auto_row)
        # ---------------------------------------------------------------------/


    def _del_empty_rank_dirs(self): # deprecated
        """ (deprecated)
        """
        for key in self.num2class_list:
            for _, value in self.rank_dict.items():
                rank_dir = self.cam_gallery_dir.joinpath(key, value)
                pngs = list(rank_dir.glob("**/*.png"))
                if len(pngs) == 0:
                    shutil.rmtree(rank_dir)
        # ---------------------------------------------------------------------/